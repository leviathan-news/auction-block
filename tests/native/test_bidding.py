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


def test_minimum_total_bid_with_active_bid(
    auction_house_with_auction, alice, payment_token, precision
):
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
    expected_min = initial_bid + (initial_bid * increment_percentage // precision)

    min_bid = house.minimum_total_bid(auction_id)
    assert min_bid == expected_min, f"Expected minimum bid {expected_min}, got {min_bid}"


def test_minimum_additional_bid_with_pending_returns(
    auction_house_with_auction, alice, bob, payment_token, precision
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
    bob_bid = initial_bid + (initial_bid * increment_percentage // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)

    # Calculate Alice's minimum additional bid
    # She should need to pay the difference between minimum total bid and her pending returns
    next_min_total = bob_bid + (bob_bid * increment_percentage // precision)
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


def test_auction_bid_by_user_no_bids(auction_house_with_auction, alice):
    """Test auction_bid_by_user when user hasn't bid"""
    auction_id = auction_house_with_auction.auction_id()

    total_bid = auction_house_with_auction.auction_bid_by_user(auction_id, alice)
    assert total_bid == 0, "Should return 0 when user hasn't bid"


def test_auction_bid_by_user_winning_bid(
    auction_house_with_auction, alice, payment_token, default_reserve_price
):
    """Test auction_bid_by_user for current winning bidder"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Place winning bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    # Check bid tracking
    total_bid = house.auction_bid_by_user(auction_id, alice)
    assert total_bid == default_reserve_price, "Should return full bid amount for winning bidder"


def test_auction_bid_by_user_outbid(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test auction_bid_by_user for outbid user"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # First bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    # Bob outbids Alice
    min_next_bid = default_reserve_price + (
        default_reserve_price * house.default_min_bid_increment_percentage() // precision
    )

    with boa.env.prank(bob):
        payment_token.approve(house.address, min_next_bid)
        house.create_bid(auction_id, min_next_bid)

    # Check bid tracking for both users
    alice_total = house.auction_bid_by_user(auction_id, alice)
    assert alice_total == default_reserve_price, "Should track Alice's outbid amount"

    bob_total = house.auction_bid_by_user(auction_id, bob)
    assert bob_total == min_next_bid, "Should track Bob's winning bid"


def test_auction_bid_by_user_multiple_bids(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test auction_bid_by_user with multiple back-and-forth bids"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Alice's first bid
    with boa.env.prank(alice):
        payment_token.approve(
            house.address, default_reserve_price * 10
        )  # Approve enough for multiple bids
        house.create_bid(auction_id, default_reserve_price)

    # Track increasing bids
    current_bid = default_reserve_price
    alice_expected_total = current_bid

    # Series of back-and-forth bids
    for _ in range(3):
        # Bob outbids
        min_next_bid = current_bid + (
            current_bid * house.default_min_bid_increment_percentage() // precision
        )
        with boa.env.prank(bob):
            payment_token.approve(house.address, min_next_bid)
            house.create_bid(auction_id, min_next_bid)
        current_bid = min_next_bid

        # Verify amounts
        alice_total = house.auction_bid_by_user(auction_id, alice)
        assert alice_total == alice_expected_total, "Should track Alice's total bids"

        bob_total = house.auction_bid_by_user(auction_id, bob)
        assert bob_total == current_bid, "Should track Bob's current winning bid"

        # Alice bids again
        min_next_bid = current_bid + (
            current_bid * house.default_min_bid_increment_percentage() // precision
        )
        with boa.env.prank(alice):
            house.create_bid(auction_id, min_next_bid)
        current_bid = min_next_bid
        alice_expected_total = current_bid

        # Verify updated amounts
        alice_total = house.auction_bid_by_user(auction_id, alice)
        assert alice_total == alice_expected_total, "Should track Alice's new total"

        bob_total = house.auction_bid_by_user(auction_id, bob)
        assert bob_total == bob_total, "Should track Bob's outbid amount"


def test_auction_bid_by_user_invalid_auction(auction_house_with_auction, alice):
    """Test auction_bid_by_user with invalid auction ID"""
    invalid_id = auction_house_with_auction.auction_id() + 1

    with pytest.raises(Exception):
        auction_house_with_auction.auction_bid_by_user(invalid_id, alice)


def test_auction_bid_by_user_after_settlement(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    deployer,
    precision,
):
    """Test auction_bid_by_user after auction is settled"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Place bids
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    min_next_bid = default_reserve_price + (
        default_reserve_price * house.default_min_bid_increment_percentage() // precision
    )
    with boa.env.prank(bob):
        payment_token.approve(house.address, min_next_bid)
        house.create_bid(auction_id, min_next_bid)

    # Record pre-settlement amounts
    alice_total_before = house.auction_bid_by_user(auction_id, alice)
    bob_total_before = house.auction_bid_by_user(auction_id, bob)

    # Time travel past auction end
    boa.env.time_travel(seconds=house.default_duration() + 1)

    # Settle auction
    with boa.env.prank(deployer):
        house.settle_auction(auction_id)

    # Verify amounts remain correct after settlement
    alice_total_after = house.auction_bid_by_user(auction_id, alice)
    bob_total_after = house.auction_bid_by_user(auction_id, bob)

    assert (
        alice_total_after == alice_total_before
    ), "Settlement shouldn't affect bid tracking for Alice"
    assert bob_total_after == bob_total_before, "Settlement shouldn't affect bid tracking for Bob"


def test_bid_with_metadata(auction_house_with_auction, alice, payment_token, ipfs_hash):
    house = auction_house_with_auction
    auction_id = house.auction_id()
    bid = house.default_reserve_price()
    with boa.env.prank(alice):
        payment_token.approve(house, bid)
        house.create_bid(auction_id, bid, ipfs_hash)
    assert house.auction_metadata(auction_id, alice) == ipfs_hash


def test_overwrite_bid_metadata(auction_house_with_auction, alice, payment_token, ipfs_hash):
    house = auction_house_with_auction
    auction_id = house.auction_id()
    bid = house.default_reserve_price()
    with boa.env.prank(alice):
        payment_token.approve(house, bid)
        house.create_bid(auction_id, bid)
        assert house.auction_metadata(auction_id, alice) == ""
        house.update_bid_metadata(auction_id, ipfs_hash)

    assert house.auction_metadata(auction_id, alice) == ipfs_hash
