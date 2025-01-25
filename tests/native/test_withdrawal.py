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
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
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
    first_bid = auction_house_with_auction.reserve_price()
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, first_bid)
        auction_house_with_auction.create_bid(auction_id, first_bid)

    # Charlie wins with higher bid
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
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
    min_increment = auction_house_with_auction.min_bid_increment_percentage()

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
    min_increment = auction_house_with_auction.min_bid_increment_percentage()

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
