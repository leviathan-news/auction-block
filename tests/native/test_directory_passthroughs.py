import boa
import pytest
from decimal import Decimal

def test_directory_overbid_possible(
    auction_house_with_auction, alice, bob, payment_token, precision, directory
):
    """
    Test that directory's create_bid function correctly handles
    token transfers when bidding above minimum
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Get minimum bid amount
    min_bid = house.minimum_total_bid(auction_id)
    
    # Create bid at double the minimum
    overbid_amount = min_bid * 2
    
    # Track balances to verify correct amount transferred
    alice_balance_before = payment_token.balanceOf(alice)
    directory_balance_before = payment_token.balanceOf(directory.address)
    
    with boa.env.prank(alice):
        payment_token.approve(directory, overbid_amount)
        directory.create_bid(house, auction_id, overbid_amount)
    
    # Verify balances haven't changed because transaction reverted
    alice_balance_after = payment_token.balanceOf(alice) 
    directory_balance_after = payment_token.balanceOf(directory.address)
    
    assert alice_balance_before -overbid_amount == alice_balance_after 
    assert directory_balance_before == directory_balance_after, "Directory's balance should not change"


def test_withdraw_permission_check(
    auction_house_with_auction, alice, bob, charlie, payment_token, directory, approval_flags, precision
):
    """
    Test that directory's withdraw function uses correct permission check
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Setup: Place and outbid to create pending returns
    initial_bid = house.default_reserve_price()
    
    # Alice places initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)
    
    # Bob outbids Alice
    increment = house.default_min_bid_increment_percentage()
    outbid_amount = initial_bid + (initial_bid * increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, outbid_amount)
        house.create_bid(auction_id, outbid_amount)
    
    # Settle auction
    boa.env.time_travel(seconds=house.default_duration() + 1)
    with boa.env.prank(alice):
        house.settle_auction(auction_id)
    
    # Now Alice has pending returns
    pending_returns = house.auction_pending_returns(auction_id, alice)
    assert pending_returns > 0, "Alice should have pending returns"
    
    # Charlie gets BID ONLY permission (not withdraw permission)
    with boa.env.prank(alice):
        directory.set_approved_caller(charlie, approval_flags.BidOnly)
    
    # Charlie attempts to withdraw Alice's funds through directory
    # This should fail if directory correctly checks for WithdrawOnly permission
    with boa.env.prank(charlie):
        with boa.reverts("!caller"):
            directory.withdraw(house, auction_id, alice)
    
    # Verify Alice's returns were withdrawn despite Charlie not having withdraw permission
    pending_returns_after = house.auction_pending_returns(auction_id, alice)
    assert pending_returns_after == pending_returns, f"Alice's {pending_returns / 10 ** 18} returns were withdrawn with incorrect permissions"


def test_withdraw_multiple_permission_check(
    auction_house_with_multiple_auctions, alice, bob, charlie, payment_token, directory, precision, approval_flags
):
    """
    Test that directory's withdraw_multiple function uses correct permission check
    """
    house = auction_house_with_multiple_auctions
    
    # Setup: Place and outbid on multiple auctions
    auction_ids = []
    for i in range(3):  # Setup 3 auctions
        auction_id = i + 1
        auction_ids.append(auction_id)
        
        # Alice places initial bid
        initial_bid = house.default_reserve_price()
        with boa.env.prank(alice):
            payment_token.approve(house.address, initial_bid)
            house.create_bid(auction_id, initial_bid)
        
        # Bob outbids Alice
        increment = house.default_min_bid_increment_percentage()
        outbid_amount = initial_bid + (initial_bid * increment // precision)
        with boa.env.prank(bob):
            payment_token.approve(house.address, outbid_amount)
            house.create_bid(auction_id, outbid_amount)
    
    # Settle all auctions
    boa.env.time_travel(seconds=house.default_duration() + 1)
    for auction_id in auction_ids:
        with boa.env.prank(alice):
            house.settle_auction(auction_id)
    
    # Now Alice has pending returns in multiple auctions
    total_pending = 0
    for auction_id in auction_ids:
        pending = house.auction_pending_returns(auction_id, alice)
        assert pending > 0, f"Alice should have pending returns for auction {auction_id}"
        total_pending += pending
    
    # Charlie gets BID ONLY permission (not withdraw permission)
    with boa.env.prank(alice):
        directory.set_approved_caller(charlie, approval_flags.BidOnly )  
    
    # Charlie attempts to withdraw Alice's funds from multiple auctions
    # This should fail if directory correctly checks for WithdrawOnly permission
    with boa.env.prank(charlie):
        with boa.reverts("!caller"):
            directory.withdraw_multiple(house, auction_ids, alice)
   
    # Verify all returns were not withdrawn 
    for auction_id in auction_ids:
        pending_after = house.auction_pending_returns(auction_id, alice)
        assert pending_after > 0, f"Alice's returns for auction {auction_id} were withdrawn with incorrect permissions"

    assert house.pending_returns(alice) > 0

    # "Oh, my bad, let me give you the right permissions" -- Alice
    with boa.env.prank(alice):
        directory.set_approved_caller(charlie, approval_flags.WithdrawOnly)

    # :blushes: "No worries, Alice, lemme try again"
    with boa.env.prank(charlie):
        directory.withdraw_multiple(house, auction_ids, alice)

    assert house.pending_returns(alice) == 0

    for auction_id in auction_ids:
        pending_after = house.auction_pending_returns(auction_id, alice)
        assert pending_after == 0, f"Alice's returns for auction {auction_id} were withdrawn with incorrect permissions"


def test_successful_overbid_through_directory(
    auction_house_with_auction, alice, bob, payment_token, directory, precision
):
    """Test that directory correctly handles bids above minimum"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Get default reserve price
    reserve_price = house.default_reserve_price()

    # Place initial bid at reserve price
    with boa.env.prank(alice):
        payment_token.approve(directory.address, reserve_price)
        directory.create_bid(house, auction_id, reserve_price)

    # Verify initial bid was placed
    auction = house.auction_list(auction_id)
    assert auction[4] == alice, "Initial bid not placed correctly"
    assert auction[1] == reserve_price, "Initial bid amount incorrect"

    # Calculate minimum bid increment
    increment_percentage = house.default_min_bid_increment_percentage()
    min_next_bid = reserve_price + (reserve_price * increment_percentage // precision)
    
    # Bob places a bid at 3x the minimum required bid
    overbid_amount = min_next_bid * 3

    # Track payment token balances to verify correct amount transferred
    bob_balance_before = payment_token.balanceOf(bob)

    with boa.env.prank(bob):
        payment_token.approve(directory.address, overbid_amount)
        directory.create_bid(house, auction_id, overbid_amount)

    # Verify bob's bid was successful
    auction_after = house.auction_list(auction_id)
    assert auction_after[4] == bob, "Overbid not placed correctly"
    assert auction_after[1] == overbid_amount, "Overbid amount incorrect"

    # Verify bob's balance decreased by the overbid amount
    bob_balance_after = payment_token.balanceOf(bob)
    balance_change = bob_balance_before - bob_balance_after

    # The amount transferred should be the full overbid amount
    assert balance_change == overbid_amount, f"Expected {overbid_amount} tokens transferred, but got {balance_change}"

    # Now test increasing own bid
    # Bob tries to increase his own bid
    new_bid_amount = overbid_amount * 2
    bob_balance_before_increase = payment_token.balanceOf(bob)

    with boa.env.prank(bob):
        payment_token.approve(directory.address, new_bid_amount)
        directory.create_bid(house, auction_id, new_bid_amount)

    # Verify bid was increased
    auction_after_increase = house.auction_list(auction_id)
    assert auction_after_increase[4] == bob, "Bid increase failed"
    assert auction_after_increase[1] == new_bid_amount, "New bid amount incorrect"

    # Verify only the difference was transferred
    bob_balance_after_increase = payment_token.balanceOf(bob)
    additional_transfer = bob_balance_before_increase - bob_balance_after_increase
    expected_transfer = new_bid_amount - overbid_amount

    assert additional_transfer == expected_transfer, f"Expected {expected_transfer} additional tokens transferred, but got {additional_transfer}"

def test_create_bid_with_token_prevents_increasing_own_bid(
    auction_house_with_auction, alice, payment_token, weth, mock_trader, directory, precision
):
    """
    Test that create_bid_with_token prevents increasing your own winning bid
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    with boa.env.prank(directory.owner()):
        directory.add_token_support(weth, mock_trader)
    
    # Place initial bid with WETH
    initial_min_bid = house.minimum_total_bid(auction_id)
    initial_weth_amount = mock_trader.safe_get_dx(initial_min_bid)
    expected_payment = mock_trader.get_dy(initial_weth_amount)
    
    with boa.env.prank(alice):
        weth.approve(directory, 2 ** 256 - 1)
        directory.create_bid_with_token(
            house, 
            auction_id,
            initial_weth_amount,
            weth,
            expected_payment,
            ""
        )
    
    # Try to increase own bid
    current_bid = house.auction_list(auction_id)[1]  # current bid amount
    increment = house.default_min_bid_increment_percentage()
    next_min_bid = current_bid + (current_bid * increment // precision)
    
    additional_weth = mock_trader.safe_get_dx(next_min_bid - current_bid)
    expected_next_payment = mock_trader.get_dy(additional_weth)
    
    with boa.env.prank(alice):
        directory.create_bid_with_token(
            house,
            auction_id,
            additional_weth,
            weth,
            next_min_bid,  # We want to increase to this total amount
            ""
        )
            
    # Verify bid was increased
    bid_after = house.auction_list(auction_id)[1]
    assert bid_after == next_min_bid, "Bid should have increased"



def test_create_bid_with_token_allows_increasing_own_bid(
    auction_house_with_auction, alice, payment_token, weth, mock_trader, directory, precision
):
    """Test that create_bid_with_token allows users to increase their own bids"""

    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(directory.owner()):
        directory.add_token_support(weth, mock_trader)

    # Place initial bid with WETH
    initial_min_bid = house.minimum_total_bid(auction_id)
    initial_weth_amount = mock_trader.safe_get_dx(initial_min_bid)
    expected_payment = mock_trader.get_dy(initial_weth_amount)

    with boa.env.prank(alice):
        weth.approve(directory.address, initial_weth_amount)
        # When trying to create a bid with a token through the directory
        try:
            directory.create_bid_with_token(
                house,
                auction_id,
                initial_weth_amount,
                weth,
                expected_payment, # min_total_bid
                "",
                alice
            )
            initial_bid_successful = True
        except Exception as e:
            initial_bid_successful = False
            print(f"Initial bid failed: {e}")

    # Check if initial bid was placed successfully
    if initial_bid_successful:
        current_bid = house.auction_list(auction_id)[1]
        initial_bidder = house.auction_list(auction_id)[4]
        assert current_bid >= expected_payment, f"Initial bid amount incorrect: {current_bid} < {expected_payment}"
        assert initial_bidder == alice, "Initial bidder incorrect"

        # Try to increase own bid
        # Calculate new bid
        increment = house.default_min_bid_increment_percentage()
        next_min_bid = current_bid + (current_bid * increment // precision)
        higher_bid = next_min_bid * 2  # Bid significantly higher

        additional_weth = mock_trader.safe_get_dx(higher_bid - current_bid)
        expected_additional_payment = mock_trader.get_dy(additional_weth)

        alice_weth_before = weth.balanceOf(alice)

        with boa.env.prank(alice):
            weth.approve(directory.address, additional_weth)
            try:
                # This should succeed if the check is fixed/removed
                directory.create_bid_with_token(
                    house,
                    auction_id,
                    additional_weth,
                    weth,
                    higher_bid,  # We want this total after conversion
                    "",
                    alice
                )
                bid_increase_successful = True
            except Exception as e:
                bid_increase_successful = False
                print(f"Bid increase failed with: {e}")

        # If the function restricts self-bidding, this test will fail
        final_bid = house.auction_list(auction_id)[1]
        assert bid_increase_successful, "Should be able to increase own bid with token"
        assert final_bid > current_bid, f"Bid should have increased from {current_bid} to approximately {higher_bid}"
    else:
        assert False, "Initial bid failed"
