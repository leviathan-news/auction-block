import boa
import pytest
from hypothesis import given, settings, strategies as st
from decimal import Decimal

@pytest.fixture(scope="session")
def auction_house_for_hypothesis(base_auction_house):
    """Session-scoped fixture for hypothesis tests"""
    return base_auction_house

# Helper to generate realistic WETH amounts (0.001 to 9.9 WETH to stay under 10 WETH limit)
weth_amounts = st.decimals(
    min_value=Decimal('0.001'),
    max_value=Decimal('9.9'),
    places=18
).map(lambda d: int(d * 10**18))

# Generate sequences of bids
bid_sequences = st.lists(
    st.tuples(
        st.booleans(),  # approve WETH?
        st.booleans(),  # approve SQUID?
        weth_amounts,   # bid amount (now capped)
    ),
    min_size=1,
    max_size=5
)

@pytest.mark.fork_only
@settings(
    deadline=None,
    max_examples=25  # Limit test cases since each fork test is slow
)
@given(bids=bid_sequences)
def test_hypothetical_bidding_scenarios(
    auction_house_for_hypothesis,
    weth_trader, 
    weth, 
    payment_token,
    make_user,
    bids,
):
    auction_house = auction_house_for_hypothesis
    
    # Setup auction
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()
    
    # Track state for verification
    current_squid_amount = 0
    bidders = {}
    
    for bid_index, (approve_weth, approve_squid, weth_amount) in enumerate(bids):
        # Create new bidder for each bid
        bidder = make_user()
        bidders[bidder] = {
            'approved_weth': False,
            'approved_squid': False,
            'weth_amount': weth_amount,
        }
        
        # Get minimum required bid in SQUID
        min_bid_squid = auction_house.default_minimum_total_bid(auction_id)
        
        try:
            # Try to get required WETH amount using safe_get_dx
            weth_needed = auction_house.safe_get_dx(weth, min_bid_squid)
            should_succeed = weth_amount >= weth_needed
        except Exception as e:
            print(f"safe_get_dx failed: {e}")
            # If safe_get_dx fails, we'll use get_dx as fallback but with extra safety margin
            try:
                weth_needed = int(weth_trader.get_dx(min_bid_squid) * 1.02)  # Add 2% buffer
                should_succeed = weth_amount >= weth_needed
            except Exception as e:
                print(f"get_dx failed too: {e}")
                should_succeed = False
        
        # Add 0.1% slippage tolerance for output verification
        min_output_with_slippage = min_bid_squid * 999 // 1000
        
        with boa.env.prank(bidder):
            # Set approvals based on test parameters
            if approve_weth:
                weth.approve(auction_house, 2**256 - 1)
                bidders[bidder]['approved_weth'] = True
            
            # For debug info
            print(f"\nBid attempt {bid_index + 1}:")
            print(f"WETH amount: {weth_amount}")
            print(f"Min SQUID needed: {min_bid_squid}")
            if 'weth_needed' in locals():
                print(f"WETH needed: {weth_needed}")
            print(f"Should succeed: {should_succeed}")
            
            # Try to place bid
            if not approve_weth:
                # Should fail without WETH approval
                with pytest.raises(Exception) as e:
                    auction_house.create_bid_with_token(
                        auction_id, 
                        weth_amount,
                        weth,
                        min_output_with_slippage,
                        bidder
                    )
                print(f"Failed as expected without approval: {e.value}")
            elif not should_succeed:
                # Should fail if bid too low
                with pytest.raises(Exception) as e:
                    auction_house.create_bid_with_token(
                        auction_id,
                        weth_amount,
                        weth, 
                        min_output_with_slippage,
                        bidder
                    )
                print(f"Failed as expected with low bid: {e.value}")
            else:
                weth_balance_before = weth.balanceOf(bidder)
                
                # Should succeed
                tx = auction_house.create_bid_with_token(
                    auction_id,
                    weth_amount,
                    weth,
                    min_output_with_slippage,
                    bidder
                )
                
                # Verify auction state
                auction = auction_house.auction_list(auction_id)
                weth_balance_after = weth.balanceOf(bidder)
                
                # Verify balances changed appropriately
                assert weth_balance_after < weth_balance_before, "WETH should be spent"
                weth_spent = weth_balance_before - weth_balance_after
                assert weth_spent <= weth_amount, f"Spent more WETH than approved: {weth_spent} > {weth_amount}"
                
                if auction[4] == bidder:  # If winning bid
                    assert auction[1] >= min_output_with_slippage, "Output should meet minimum with slippage"
                    current_squid_amount = auction[1]
                    print(f"Successful bid! Amount: {current_squid_amount}")
                else:  # If outbid
                    pending = auction_house.pending_returns(auction_id, bidder)
                    assert pending > 0, "Should have pending returns if outbid"
                    print(f"Outbid. Pending returns: {pending}")

@pytest.mark.fork_only
def test_edge_case_scenarios(
    auction_house,
    weth_trader,
    weth,
    payment_token,
    make_user
):
    """Test specific edge cases like minimum bids and exact increments"""
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()

    # Test minimum valid bid
    bidder = make_user()
    min_squid = auction_house.minimum_total_bid(auction_id)
    min_weth = auction_house.safe_get_dx(weth, min_squid)  # Use safe_get_dx
    
    # Add 0.1% slippage buffer
    min_output_with_slippage = min_squid * 999 // 1000

    with boa.env.prank(bidder):
        weth.approve(auction_house, 2**256 - 1)
        payment_token.approve(auction_house, 2**256 - 1)

        # Bid with slippage tolerance
        auction_house.create_bid_with_token(
            auction_id,
            min_weth,
            weth,
            min_output_with_slippage,
            bidder
        )

        # Verify it worked
        auction = auction_house.auction_list(auction_id)
        assert auction[4] == bidder

    # Test exact increment scenario
    next_bidder = make_user()
    min_increment = auction_house.min_bid_increment_percentage()
    current_squid = auction_house.auction_list(auction_id)[1]
    
    # Calculate exact increment in SQUID with safe margin
    exact_increment_squid = current_squid + (current_squid * min_increment // 100)
    exact_increment_weth = auction_house.safe_get_dx(weth, exact_increment_squid)
    min_output_with_slippage = exact_increment_squid * 999 // 1000

    with boa.env.prank(next_bidder):
        weth.approve(auction_house, 2**256 - 1)
        auction_house.create_bid_with_token(
            auction_id,
            exact_increment_weth,
            weth,
            min_output_with_slippage,
            next_bidder
        )
        
        # Verify
        auction = auction_house.auction_list(auction_id)
        assert auction[4] == next_bidder
        assert auction[1] >= min_output_with_slippage
