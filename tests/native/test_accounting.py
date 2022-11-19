import boa
import pytest


def test_bid_accounting_initial_state(
    auction_house_with_auction, alice, payment_token, default_reserve_price
):
    """Test initial bid accounting state"""
    auction_id = auction_house_with_auction.auction_id()

    # Initially no bids
    assert auction_house_with_auction.auction_bid_by_user(auction_id, alice) == 0
    assert auction_house_with_auction.pending_returns(alice) == 0

    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Should now have winning bid but no pending returns
    assert (
        auction_house_with_auction.auction_bid_by_user(auction_id, alice) == default_reserve_price
    )
    assert auction_house_with_auction.pending_returns(alice) == 0


def test_bid_accounting_outbid_sequence(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test accounting through a sequence of outbids"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Bob outbids
    bob_bid = default_reserve_price + (default_reserve_price * min_increment) // precision
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_bid)
        auction_house_with_auction.create_bid(auction_id, bob_bid)

    # Alice's bid should now be in pending returns
    assert (
        auction_house_with_auction.auction_bid_by_user(auction_id, alice) == default_reserve_price
    )
    assert auction_house_with_auction.pending_returns(alice) == default_reserve_price
    # Bob should have winning bid but no pending
    assert auction_house_with_auction.auction_bid_by_user(auction_id, bob) == bob_bid
    assert auction_house_with_auction.pending_returns(bob) == 0


def test_bid_accounting_self_rebid(
    auction_house_with_auction, alice, payment_token, default_reserve_price, precision
):
    """Test accounting when increasing own bid"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price * 10)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Record state after initial bid
    assert (
        auction_house_with_auction.auction_bid_by_user(auction_id, alice) == default_reserve_price
    )
    assert auction_house_with_auction.pending_returns(alice) == 0

    # Increase own bid
    increased_bid = default_reserve_price + (default_reserve_price * min_increment) // precision
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, increased_bid)

    # Should still have no pending returns, just higher winning bid
    assert auction_house_with_auction.auction_bid_by_user(auction_id, alice) == increased_bid
    assert auction_house_with_auction.pending_returns(alice) == 0


def test_bid_accounting_insufficient_total(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test attempts to bid with insufficient total (pending + new tokens)"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Bob outbids
    bob_bid = default_reserve_price + (default_reserve_price * min_increment) // precision
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_bid)
        auction_house_with_auction.create_bid(auction_id, bob_bid)

    # At this point Alice has default_reserve_price in pending returns
    assert auction_house_with_auction.pending_returns(alice) == default_reserve_price

    # Try various insufficient bids
    with boa.env.prank(alice):
        # Approve less than needed on top of pending returns
        small_approve = (bob_bid - default_reserve_price) // 2
        payment_token.approve(auction_house_with_auction.address, small_approve)

        # Try to bid way more than total available
        large_bid = bob_bid * 2
        with pytest.raises(Exception):
            auction_house_with_auction.create_bid(auction_id, large_bid)

        # Verify state unchanged
        assert auction_house_with_auction.pending_returns(alice) == default_reserve_price
        assert auction_house_with_auction.auction_list(auction_id)[4] == bob  # Still winning


def test_bid_accounting_exact_returns_usage(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test bids that exactly use up pending returns"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Bob outbids
    bob_bid = default_reserve_price + (default_reserve_price * min_increment) // precision
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_bid)
        auction_house_with_auction.create_bid(auction_id, bob_bid)

    # Alice has default_reserve_price in pending returns
    assert auction_house_with_auction.pending_returns(alice) == default_reserve_price

    # Alice tries to bid exactly her pending returns
    # Should fail because needs to be higher than current bid
    with boa.env.prank(alice):
        with boa.reverts("!increment"):
            auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Verify state unchanged
    assert auction_house_with_auction.pending_returns(alice) == default_reserve_price
    assert auction_house_with_auction.auction_list(auction_id)[4] == bob


def test_bid_accounting_multiple_pending_returns(
    auction_house_with_auction, alice, bob, charlie, payment_token, default_reserve_price, precision
):
    """Test managing multiple users' pending returns through a sequence of bids"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Everyone approves a large amount
    initial_approve = default_reserve_price * 10
    for bidder in [alice, bob, charlie]:
        with boa.env.prank(bidder):
            payment_token.approve(auction_house_with_auction.address, initial_approve)

    # Sequence of bids, tracking expected returns
    bid_amounts = []

    # Alice's initial bid
    bid_amounts.append(default_reserve_price)
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, bid_amounts[0])

    # Bob outbids
    bid_amounts.append(bid_amounts[0] + (bid_amounts[0] * min_increment) // precision)
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(auction_id, bid_amounts[1])

    # Charlie outbids
    bid_amounts.append(bid_amounts[1] + (bid_amounts[1] * min_increment) // precision)
    with boa.env.prank(charlie):
        auction_house_with_auction.create_bid(auction_id, bid_amounts[2])

    # Verify returns
    assert auction_house_with_auction.pending_returns(alice) == bid_amounts[0]
    assert auction_house_with_auction.pending_returns(bob) == bid_amounts[1]
    assert auction_house_with_auction.pending_returns(charlie) == 0  # Winning bid

    # Bob uses returns plus extra for higher bid
    next_bid = bid_amounts[2] + (bid_amounts[2] * min_increment) // precision
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(auction_id, next_bid)

    # Verify updated state
    assert auction_house_with_auction.pending_returns(alice) == bid_amounts[0]  # Unchanged
    assert auction_house_with_auction.pending_returns(bob) == 0  # Used in bid
    assert (
        auction_house_with_auction.pending_returns(charlie) == bid_amounts[2]
    )  # Previous winning bid

    # Alice tries to use pending returns but insufficient for high bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 0)  # Remove approval
        with boa.reverts():  # Should fail on transfer since insufficient approval
            auction_house_with_auction.create_bid(auction_id, next_bid * 2)  # Way too high

    # Returns should be unchanged after failed bid
    assert auction_house_with_auction.pending_returns(alice) == bid_amounts[0]
