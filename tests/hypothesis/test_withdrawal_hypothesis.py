import boa
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from typing import List, Tuple

pytestmark = pytest.mark.fork_only


# Helper strategy to generate auction IDs and bid amounts
auction_ids = st.integers(min_value=1, max_value=10)
bid_amounts = st.integers(min_value=10**17, max_value=10**19)  # 0.1 to 10 tokens

# Strategy for generating sequences of withdrawal attempts
withdrawal_sequences = st.lists(
    st.tuples(auction_ids, bid_amounts),
    min_size=1,
    max_size=5
)

def setup_auction_with_outbid(
    auction_house,
    payment_token,
    bidder,
    outbidder,
    bid_amount,
    outbid_amount
) -> Tuple[int, int]:
    """Helper to setup an auction with an outbid scenario"""
    owner = auction_house.owner()
    
    # Create auction
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()
    
    # First bid
    with boa.env.prank(bidder):
        payment_token.approve(auction_house, bid_amount)
        auction_house.create_bid(auction_id, bid_amount)
    
    # Outbid
    with boa.env.prank(outbidder):
        payment_token.approve(auction_house, outbid_amount)
        auction_house.create_bid(auction_id, outbid_amount)
        
    return auction_id, bid_amount

# ============================================================================================
# 1. Withdrawal Timing Attack Tests
# ============================================================================================

def test_cannot_withdraw_during_active_bid(
    auction_house,
    payment_token,
    alice,
    bob
):
    """Test that a user cannot withdraw while they are the highest bidder"""
    owner = auction_house.owner()
    
    # Create auction
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()
    
    bid_amount = auction_house.minimum_total_bid(auction_id)
    
    # Place bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house, bid_amount)
        auction_house.create_bid(auction_id, bid_amount)
        
        # Attempt withdrawal while highest bidder
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id)

def test_withdrawal_after_auction_end(
    auction_house,
    payment_token,
    alice,
    bob
):
    """Test withdrawals immediately after auction ends"""
    bid_amount = 10**18
    outbid_amount = bid_amount * 2
    
    auction_id, _ = setup_auction_with_outbid(
        auction_house,
        payment_token,
        alice,
        bob,
        bid_amount,
        outbid_amount
    )
    
    # Fast forward past auction end
    auction = auction_house.auction_list(auction_id)
    boa.env.time_travel(seconds=auction[3] - auction[2] + 1)
    
    # Withdrawal should still work after auction ends
    initial_balance = payment_token.balanceOf(alice)
    with boa.env.prank(alice):
        auction_house.withdraw(auction_id)
    
    assert payment_token.balanceOf(alice) == initial_balance + bid_amount

# ============================================================================================
# 2. Multiple Withdrawal Attempt Tests
# ============================================================================================

def test_double_withdrawal_prevention(
    auction_house,
    payment_token,
    alice,
    bob
):
    """Test that double withdrawals are prevented"""
    bid_amount = 10**18
    outbid_amount = bid_amount * 2
    
    auction_id, _ = setup_auction_with_outbid(
        auction_house,
        payment_token,
        alice,
        bob,
        bid_amount,
        outbid_amount
    )
    
    # First withdrawal
    with boa.env.prank(alice):
        auction_house.withdraw(auction_id)
        
    # Second withdrawal attempt should fail
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id)

@pytest.mark.parametrize("num_withdrawals", [1, 5, 10])
def test_multiple_withdrawal_stress(
    auction_house,
    payment_token,
    alice,
    bob,
    num_withdrawals
):
    """Stress test multiple withdrawal attempts"""
    owner = auction_house.owner()
    total_pending = 0
    auction_ids = []
    
    # Setup multiple auctions with outbids
    for _ in range(num_withdrawals):
        bid_amount = 10**18 * (_ + 1)  # Increasing bids
        outbid_amount = bid_amount * 2
        
        auction_id, amount = setup_auction_with_outbid(
            auction_house,
            payment_token,
            alice,
            bob,
            bid_amount,
            outbid_amount
        )
        auction_ids.append(auction_id)
        total_pending += bid_amount
    
    # Try withdrawing from all auctions
    initial_balance = payment_token.balanceOf(alice)
    with boa.env.prank(alice):
        auction_house.withdraw_multiple(auction_ids)
    
    # Verify total withdrawn amount
    assert payment_token.balanceOf(alice) == initial_balance + total_pending
    
    # Verify no pending returns remain
    for auction_id in auction_ids:
        assert auction_house.auction_pending_returns(auction_id, alice) == 0

# ============================================================================================
# 3. Cross-Auction Withdrawal Tests
# ============================================================================================

def test_cross_auction_withdrawal_independence(
    auction_house,
    payment_token,
    alice,
    bob
):
    """Test that withdrawals from one auction don't affect others"""
    # Setup two auctions
    bid_amount1 = 10**18
    bid_amount2 = 2 * 10**18
    outbid_amount1 = bid_amount1 * 2
    outbid_amount2 = bid_amount2 * 2
    
    auction_id1, _ = setup_auction_with_outbid(
        auction_house,
        payment_token,
        alice,
        bob,
        bid_amount1,
        outbid_amount1
    )
    
    auction_id2, _ = setup_auction_with_outbid(
        auction_house,
        payment_token,
        alice,
        bob,
        bid_amount2,
        outbid_amount2
    )
    
    # Withdraw from first auction
    with boa.env.prank(alice):
        auction_house.withdraw(auction_id1)
    
    # Verify second auction's pending returns unaffected
    assert auction_house.auction_pending_returns(auction_id2, alice) == bid_amount2

@given(st.lists(auction_ids, min_size=2, max_size=5, unique=True))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=10)
def test_withdrawal_sequence_invariants(
    auction_house,
    payment_token,
    alice,
    bob,
    auction_id_sequence
):
    """Property-based test for withdrawal sequence invariants"""
    owner = auction_house.owner()
    total_pending = 0
    valid_ids = []
    
    # Setup multiple auctions with different bid amounts
    for auction_id in auction_id_sequence:
        bid_amount = 10**18 * auction_id  # Different amounts for different auctions
        outbid_amount = bid_amount * 2
        
        # Create auction with specific ID
        with boa.env.prank(owner):
            current_id = auction_house.create_new_auction()
            if current_id == auction_id:
                valid_ids.append(auction_id)
                # Setup bids
                with boa.env.prank(alice):
                    payment_token.approve(auction_house, bid_amount)
                    auction_house.create_bid(auction_id, bid_amount)
                with boa.env.prank(bob):
                    payment_token.approve(auction_house, outbid_amount)
                    auction_house.create_bid(auction_id, outbid_amount)
                total_pending += bid_amount
    
    if valid_ids:
        # Try different withdrawal sequences
        initial_balance = payment_token.balanceOf(alice)
        remaining_ids = valid_ids.copy()
        
        while remaining_ids:
            withdraw_id = remaining_ids.pop(0)
            with boa.env.prank(alice):
                auction_house.withdraw(withdraw_id)
            
            # Verify invariants after each withdrawal
            current_balance = payment_token.balanceOf(alice)
            assert current_balance > initial_balance
            assert current_balance <= initial_balance + total_pending
            
            # Check remaining pending returns
            for auction_id in remaining_ids:
                assert auction_house.auction_pending_returns(auction_id, alice) > 0

# ============================================================================================
# 4. Withdrawal Permission/Delegation Tests
# ============================================================================================

def test_unauthorized_withdrawal_prevention(
    auction_house,
    payment_token,
    alice,
    bob,
    charlie
):
    """Test that unauthorized withdrawals are prevented"""
    bid_amount = 10**18
    outbid_amount = bid_amount * 2
    
    auction_id, _ = setup_auction_with_outbid(
        auction_house,
        payment_token,
        alice,
        bob,
        bid_amount,
        outbid_amount
    )
    
    # Attempt unauthorized withdrawal
    with boa.env.prank(charlie):
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id, alice)

# ============================================================================================
# 5. Edge Cases and Boundary Tests
# ============================================================================================

def test_zero_pending_returns(
    auction_house,
    payment_token,
    alice
):
    """Test withdrawal behavior with zero pending returns"""
    owner = auction_house.owner()
    
    # Create auction
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()
    
    # Attempt withdrawal without any bids
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id)

def test_withdrawal_from_nonexistent_auction(
    auction_house,
    alice
):
    """Test withdrawal attempts from non-existent auctions"""
    non_existent_id = 999
    
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw(non_existent_id)

def test_empty_withdrawal_array(
    auction_house,
    alice
):
    """Test withdrawal_multiple with empty array"""
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw_multiple([])

@given(st.lists(
    st.integers(min_value=1000, max_value=9999),  # Non-existent auction IDs
    min_size=1,
    max_size=5,
    unique=True
))
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=10
)
def test_invalid_withdrawal_sequences(
    auction_house,
    alice,
    invalid_ids
):
    """Property-based test for invalid withdrawal sequences"""
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw_multiple(invalid_ids)

def test_max_withdrawals_limit(
    auction_house,
    payment_token,
    alice,
    bob
):
    """Test behavior at MAX_WITHDRAWALS limit"""
    MAX_WITHDRAWALS = 100  # From contract
    auction_ids = []
    
    # Setup maximum number of auctions with pending returns
    for i in range(MAX_WITHDRAWALS + 1):
        bid_amount = 10**18
        outbid_amount = bid_amount * 2
        
        auction_id, _ = setup_auction_with_outbid(
            auction_house,
            payment_token,
            alice,
            bob,
            bid_amount,
            outbid_amount
        )
        auction_ids.append(auction_id)
    
    # Attempt to withdraw from more than MAX_WITHDRAWALS auctions
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw_multiple(auction_ids)
    
    # Should succeed with exactly MAX_WITHDRAWALS
    with boa.env.prank(alice):
        auction_house.withdraw_multiple(auction_ids[:MAX_WITHDRAWALS])
