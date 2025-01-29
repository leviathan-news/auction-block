import boa
import pytest


def test_minimum_total_bid_no_bids(auction_house_with_auction):
    """Test minimum total bid calculation when there are no bids"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Should return reserve price when there are no bids
    min_bid = house.minimum_total_bid(auction_id)
    assert (
        min_bid == house.default_reserve_price()
    ), "Minimum bid should equal reserve price when no bids exist"


def test_minimum_additional_bid_no_bids(auction_house_with_auction, alice):
    """Test minimum additional bid calculation when there are no bids"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # For a new bidder with no pending returns, should equal reserve price
    min_additional = house.minimum_additional_bid_for_user(auction_id, alice)
    assert (
        min_additional == house.default_reserve_price()
    ), "Minimum additional bid should equal reserve price for new bidder"


def test_minimum_total_bid_with_active_bid(auction_house_with_auction, alice, payment_token):
    """Test minimum total bid calculation with an active bid"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Place initial bid at reserve price
    initial_bid = house.default_reserve_price()
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)

    # Calculate expected minimum next bid
    increment_percentage = house.default_min_bid_increment_percentage()
    expected_min = initial_bid + (initial_bid * increment_percentage // 100)

    min_bid = house.minimum_total_bid(auction_id)
    assert min_bid == expected_min, f"Expected minimum bid {expected_min}, got {min_bid}"


def test_minimum_additional_bid_with_pending_returns(
    auction_house_with_auction, alice, bob, payment_token
):
    """Test minimum additional bid calculation when bidder has pending returns"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Alice places initial bid
    initial_bid = house.default_reserve_price()
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)

    # Bob outbids Alice
    increment_percentage = house.default_min_bid_increment_percentage()
    bob_bid = initial_bid + (initial_bid * increment_percentage // 100)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)

    # Calculate Alice's minimum additional bid
    # She should need to pay the difference between minimum total bid and her pending returns
    next_min_total = bob_bid + (bob_bid * increment_percentage // 100)
    alice_pending = house.pending_returns(alice)
    expected_additional = next_min_total - alice_pending

    min_additional = house.minimum_additional_bid_for_user(auction_id, alice)
    assert (
        min_additional == expected_additional
    ), f"Expected minimum additional bid {expected_additional}, got {min_additional}"


def test_minimum_bids_invalid_auction(auction_house):
    """Test minimum bid calculations for non-existent auction"""
    with boa.reverts():  # Should revert due to invalid auction ID
        auction_house.minimum_total_bid(999)

    with boa.reverts():  # Should revert due to invalid auction ID
        auction_house.minimum_additional_bid_for_user(999, boa.env.generate_address())


def test_minimum_bids_settled_auction(auction_house_with_auction, deployer):
    """Test minimum bid calculations for settled auction"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Fast forward past auction end
    auction = house.auction_list(auction_id)
    time_to_end = auction[3] - auction[2]
    boa.env.time_travel(seconds=time_to_end + 1)

    # Settle the auction
    with boa.env.prank(deployer):
        house.settle_auction(auction_id)

    # Both functions should revert for settled auction
    with boa.reverts():
        house.minimum_total_bid(auction_id)

    with boa.reverts():
        house.minimum_additional_bid_for_user(auction_id, boa.env.generate_address())
