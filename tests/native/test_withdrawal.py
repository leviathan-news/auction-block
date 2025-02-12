import boa
import pytest
from eth_utils import to_wei


def test_withdraw_stale(
    auction_house_with_auction,
    deployer,
    alice,
    bob,
    payment_token,
    fee_receiver,
    default_reserve_price,
):
    """Test admin withdrawal of stale pending returns"""
    balance_of_alice_before = payment_token.balanceOf(alice)
    balance_of_fee_receiver_before = payment_token.balanceOf(fee_receiver)
    balance_of_owner_before = payment_token.balanceOf(deployer)

    auction_id = auction_house_with_auction.auction_id()

    # Create pending returns
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Bob outbids
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    next_bid = default_reserve_price + (default_reserve_price * min_increment) // 100
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, next_bid)
        auction_house_with_auction.create_bid(auction_id, next_bid)

    # Settlement
    boa.env.time_travel(seconds=4000)
    with boa.env.prank(deployer):
        auction_house_with_auction.settle_auction(auction_id)

    # Admin stale withdrawal
    assert auction_house_with_auction.auction_pending_returns(auction_id, alice) > 0
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice])

    # Calculate expected fee distribution
    stale_fee = default_reserve_price * 5 // 100
    return_amount = default_reserve_price - stale_fee
    fee_from_bid = next_bid * auction_house_with_auction.fee() // 100
    owner_share = next_bid - fee_from_bid

    # Verify balances
    assert auction_house_with_auction.auction_pending_returns(auction_id, alice) == 0
    assert (
        payment_token.balanceOf(alice)
        == balance_of_alice_before - default_reserve_price + return_amount
    )
    assert (
        payment_token.balanceOf(fee_receiver)
        == balance_of_fee_receiver_before + fee_from_bid + stale_fee
    )
    assert payment_token.balanceOf(deployer) == balance_of_owner_before + owner_share


def test_withdraw_stale_multiple_users(
    auction_house_with_auction, alice, bob, charlie, deployer, payment_token, fee_receiver
):
    """Test admin withdrawal for multiple users with various states"""
    auction_id = auction_house_with_auction.auction_id()

    # Track initial balances
    balances_before = {
        alice: payment_token.balanceOf(alice),
        bob: payment_token.balanceOf(bob),
        charlie: payment_token.balanceOf(charlie),
        fee_receiver: payment_token.balanceOf(fee_receiver),
        deployer: payment_token.balanceOf(deployer),
    }

    # Bob bids first
    first_bid = auction_house_with_auction.default_reserve_price()
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, first_bid)
        auction_house_with_auction.create_bid(auction_id, first_bid)

    # Charlie wins with higher bid
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    second_bid = first_bid + (first_bid * min_increment) // 100
    with boa.env.prank(charlie):
        payment_token.approve(auction_house_with_auction.address, second_bid)
        auction_house_with_auction.create_bid(auction_id, second_bid)

    # Settlement
    boa.env.time_travel(seconds=4000)
    with boa.env.prank(deployer):
        auction_house_with_auction.settle_auction(auction_id)

    # Admin withdraws stale returns for all users
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice, bob, charlie])

    # Calculate expected amounts
    stale_fee = first_bid * 5 // 100  # 5% fee on Bob's stale return
    bob_return = first_bid - stale_fee
    fee_from_bid = second_bid * auction_house_with_auction.fee() // 100
    owner_share = second_bid - fee_from_bid

    # Verify final balances
    assert payment_token.balanceOf(alice) == balances_before[alice]  # Unchanged
    assert payment_token.balanceOf(bob) == balances_before[bob] - first_bid + bob_return
    assert payment_token.balanceOf(charlie) == balances_before[charlie] - second_bid
    assert (
        payment_token.balanceOf(fee_receiver)
        == balances_before[fee_receiver] + stale_fee + fee_from_bid
    )
    assert payment_token.balanceOf(deployer) == balances_before[deployer] + owner_share


def test_create_bid_with_pending_returns(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price
):
    """Test using pending returns for a new bid"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Calculate bid amounts
    initial_bid = default_reserve_price
    bob_bid = initial_bid + (initial_bid * min_increment) // 100
    final_bid = bob_bid + (bob_bid * min_increment) // 100
    additional_amount = final_bid - initial_bid

    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, initial_bid)
        auction_house_with_auction.create_bid(auction_id, initial_bid)

    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_bid)
        auction_house_with_auction.create_bid(auction_id, bob_bid)

    # Verify Alice's pending returns
    assert auction_house_with_auction.pending_returns(alice) == initial_bid

    # Alice uses pending returns plus additional tokens for new higher bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, additional_amount)
        auction_house_with_auction.create_bid(auction_id, final_bid)

    auction = auction_house_with_auction.auction_list(auction_id)
    assert auction[4] == alice  # bidder
    assert auction[1] == final_bid  # amount
    assert auction_house_with_auction.pending_returns(alice) == 0  # Used up pending returns


def test_create_bid_insufficient_pending_returns(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price
):
    """Test bid fails when pending returns aren't enough"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Calculate bid amounts
    initial_bid = default_reserve_price
    bob_bid = initial_bid + (initial_bid * min_increment) // 100
    attempted_bid = bob_bid * 2  # Try to bid way higher

    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, initial_bid)
        auction_house_with_auction.create_bid(auction_id, initial_bid)

    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_bid)
        auction_house_with_auction.create_bid(auction_id, bob_bid)

    # Alice tries to bid too high with insufficient returns and insufficient approval
    with boa.env.prank(alice):
        # Only approve a small amount, not enough with pending returns
        payment_token.approve(auction_house_with_auction.address, initial_bid)
        with boa.reverts():  # Expected to fail on token transfer
            auction_house_with_auction.create_bid(auction_id, attempted_bid)

    # State should be unchanged
    auction = auction_house_with_auction.auction_list(auction_id)
    assert auction[4] == bob  # still bob's bid
    assert auction[1] == bob_bid  # amount unchanged
    assert auction_house_with_auction.pending_returns(alice) == initial_bid


def test_prevent_bid_cycling_attack(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
):
    """
    Test that the contract prevents bid cycling attacks by not allowing
    withdrawals during active auctions.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = initial_bid + (initial_bid * min_increment // 100)
    
    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)
        
    # Step 2: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)
        
    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == initial_bid, "Alice should have pending returns"
    
    # Step 3: Attempt to withdraw during active auction - should fail
    with boa.env.prank(alice):
        with boa.reverts("!inactive"):
            house.withdraw(auction_id)
    
    # Verify Alice's balance hasn't changed - withdrawal was prevented
    assert payment_token.balanceOf(alice) == initial_balance_alice - initial_bid, \
        "Alice's balance should still be reduced by initial bid amount"
    
    # Verify auction state remains unchanged
    auction = house.auction_list(auction_id)
    assert auction[4] == bob, "Bob should still be winning bidder"
    assert auction[1] == second_bid, "Bid amount should be unchanged"
    assert house.pending_returns(alice) == initial_bid, "Pending returns should be unchanged"
    
    # Now end the auction and verify withdrawal works
    boa.env.time_travel(seconds=4000)  # Past auction end
    
    with boa.env.prank(alice):
        house.withdraw(auction_id)
        
    # Verify withdrawal succeeded after auction ended
    assert payment_token.balanceOf(alice) == initial_balance_alice, \
        "Alice should get her funds back after auction ends"
    assert house.pending_returns(alice) == 0, "Pending returns should be cleared"

def test_prevent_withdrawal_during_active_auction(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
):
    """
    Security test to ensure users CANNOT withdraw pending returns while an auction
    is still active. Test should fail if this vulnerability exists.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = initial_bid + (initial_bid * min_increment // 100)
    
    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)
        
    # Step 2: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)
        
    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == initial_bid, "Setup failed: Alice should have pending returns"
    
    # Attempt to withdraw during active auction - this should fail
    with boa.env.prank(alice):
        # This should revert because auction is still active
        with boa.reverts():
            house.withdraw(auction_id)
    
    # Double-check Alice couldn't withdraw by verifying her balance hasn't changed
    assert payment_token.balanceOf(alice) == initial_balance_alice - initial_bid, \
        "Security vulnerability: User was able to withdraw during active auction!"
    
    # Now properly end the auction
    boa.env.time_travel(seconds=4000)  # Past auction end time
    
    # Now withdrawal should succeed
    with boa.env.prank(alice):
        house.withdraw(auction_id)
        
    # Verify withdrawal worked after auction ended
    assert payment_token.balanceOf(alice) == initial_balance_alice, \
        "Withdrawal failed after auction ended"


def test_prevent_multi_auction_withdrawal_manipulation(
    auction_house_with_auction,
    alice,
    bob,
    deployer,
    payment_token,
    default_reserve_price,
):
    """
    Test to prevent users from using pending returns from one auction
    to bid on another auction while both are active.
    """
    house = auction_house_with_auction
    auction1_id = house.auction_id()
    
    # Create a second auction
    with boa.env.prank(deployer):
        auction2_id = house.create_new_auction()
        
    # Initial bid on first auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction1_id, default_reserve_price)
    
    # Bob outbids on first auction
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = default_reserve_price + (default_reserve_price * min_increment // 100)
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction1_id, second_bid)
        
    # Attempt to use pending returns from auction1 to bid on auction2
    with boa.env.prank(alice):
        with boa.reverts():
            house.create_bid(auction2_id, default_reserve_price)




def test_prevent_withdrawal_amount_manipulation(
    auction_house_with_auction,
    alice,
    bob,
    charlie,
    payment_token,
    default_reserve_price,
):
    """
    Test to prevent manipulation of withdrawal amounts through
    complex bidding patterns.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Create a series of bids and outbids
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 2)
        house.create_bid(auction_id, default_reserve_price)
    
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // 100)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)
        
    charlie_bid = bob_bid + (bob_bid * min_increment // 100)
    with boa.env.prank(charlie):
        payment_token.approve(house.address, charlie_bid)
        house.create_bid(auction_id, charlie_bid)
    
    # End auction
    boa.env.time_travel(seconds=4000)
    
    # Verify withdrawal amount matches original bid exactly
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    
    assert payment_token.balanceOf(alice) == initial_balance_alice, \
        "Withdrawal amount does not match expected value"


def test_prevent_cross_auction_balance_manipulation(
    auction_house_with_auction,
    alice,
    bob,
    deployer,
    payment_token,
    default_reserve_price,
):
    """
    Test to prevent users from manipulating their balances across multiple
    auctions to get more funds out than they put in.
    """
    house = auction_house_with_auction
    auction1_id = house.auction_id()
    
    # Create a second auction
    with boa.env.prank(deployer):
        auction2_id = house.create_new_auction()
    
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Bid on first auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction1_id, default_reserve_price)
    
    # Get outbid on first auction
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // 100)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction1_id, bob_bid)
    
    # Try to bid on second auction
    with boa.env.prank(alice):
        with boa.reverts():
            house.create_bid(auction2_id, default_reserve_price)
    
    # End first auction and withdraw
    boa.env.time_travel(seconds=4000)
    with boa.env.prank(alice):
        house.withdraw(auction1_id)
    
    # Verify total withdrawable never exceeds total deposited
    assert payment_token.balanceOf(alice) <= initial_balance_alice, \
        "User was able to withdraw more than they deposited"
