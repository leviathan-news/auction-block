from typing import Tuple

import boa
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


def build_bid_strategy(reserve_price, multiplier=100):
    """
    Dynamically generate a bid strategy based on the current reserve price

    Args:
        reserve_price (int): The current reserve price for the auction
        multiplier (int, optional): Maximum bid as a multiple of reserve price. Defaults to 100.

    Returns:
        A hypothesis strategy for generating valid bid amounts
    """
    return st.integers(
        min_value=int(reserve_price),  # Minimum is the reserve price
        max_value=int(reserve_price * multiplier),  # Maximum set to multiplier times reserve price
    )


def setup_auction_with_outbid(
    auction_house,
    payment_token,
    bidder,
    outbidder,
    bid_amount,
    outbid_amount,
    auction_struct,
    advance_time: bool = True,
) -> Tuple[int, int]:
    """Helper to setup an auction with an outbid scenario"""
    owner = auction_house.owner()

    # Create auction
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Get the reserve price and minimum increment
    reserve_price = auction_house.default_reserve_price()
    min_increment = auction_house.default_min_bid_increment_percentage()
    precision = 100 * 10**8  # From the contract's precision constant

    # Ensure initial bid meets reserve price
    initial_bid = max(bid_amount, reserve_price)

    # First bid
    with boa.env.prank(bidder):
        payment_token.approve(auction_house, initial_bid)
        auction_house.create_bid(auction_id, initial_bid)

    # Calculate minimum next bid
    min_next_bid = initial_bid + (initial_bid * min_increment // precision)
    outbid_amount = max(outbid_amount, min_next_bid)

    # Outbid
    with boa.env.prank(outbidder):
        payment_token.approve(auction_house, outbid_amount)
        auction_house.create_bid(auction_id, outbid_amount)

    if advance_time:
        # Move past auction end
        auction = auction_house.auction_list(auction_id)
        time_to_advance = (
            auction[auction_struct.end_time] - auction[auction_struct.start_time] + 100
        )
        boa.env.time_travel(seconds=time_to_advance)

    return auction_id, initial_bid


def test_cannot_withdraw_during_active_bid(auction_house, payment_token, alice, bob):
    """Test that a user cannot withdraw while they are the highest bidder"""
    owner = auction_house.owner()
    reserve_price = auction_house.default_reserve_price()

    # Create auction
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Place bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house, reserve_price)
        auction_house.create_bid(auction_id, reserve_price)

        # Attempt withdrawal while highest bidder
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id)


def test_withdrawal_after_auction_end(auction_house, payment_token, alice, bob, auction_struct):
    """Test withdrawals immediately after auction ends"""
    reserve_price = auction_house.default_reserve_price()
    outbid_amount = reserve_price * 2

    auction_id, initial_bid = setup_auction_with_outbid(
        auction_house, payment_token, alice, bob, reserve_price, outbid_amount, auction_struct
    )

    # Settle and withdraw
    initial_balance = payment_token.balanceOf(alice)
    with boa.env.prank(alice):
        auction_house.settle_auction(auction_id)
        auction_house.withdraw(auction_id)

    assert payment_token.balanceOf(alice) == initial_balance + initial_bid


def test_double_withdrawal_prevention(auction_house, payment_token, alice, bob, auction_struct):
    """Test that double withdrawals are prevented"""
    reserve_price = auction_house.default_reserve_price()
    outbid_amount = reserve_price * 2

    auction_id, _ = setup_auction_with_outbid(
        auction_house, payment_token, alice, bob, reserve_price, outbid_amount, auction_struct
    )

    # First withdrawal
    with boa.env.prank(alice):
        auction_house.settle_auction(auction_id)
        auction_house.withdraw(auction_id)

    # Second withdrawal attempt should fail
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id)


@pytest.mark.parametrize("num_withdrawals", [1, 5, 10])
def test_multiple_withdrawal_stress(
    auction_house, payment_token, alice, bob, num_withdrawals, auction_struct
):
    """Stress test multiple withdrawal attempts"""
    total_pending = 0
    auction_ids = []

    # Setup multiple auctions with outbids
    for _ in range(num_withdrawals):
        reserve_price = auction_house.default_reserve_price()
        bid_amount = reserve_price
        outbid_multiple = _ + 2  # Ensure incrementing bids
        outbid_amount = reserve_price * outbid_multiple

        auction_id, amount = setup_auction_with_outbid(
            auction_house,
            payment_token,
            alice,
            bob,
            bid_amount,
            outbid_amount,
            auction_struct,
            advance_time=True,
        )
        auction_ids.append(auction_id)
        auction_house.settle_auction(auction_id)
        total_pending += amount

    # Try withdrawing from all auctions
    initial_balance = payment_token.balanceOf(alice)
    with boa.env.prank(alice):
        auction_house.withdraw_multiple(auction_ids)

    # Verify total withdrawn amount
    assert payment_token.balanceOf(alice) == initial_balance + total_pending

    # Verify no pending returns remain
    for auction_id in auction_ids:
        assert auction_house.auction_pending_returns(auction_id, alice) == 0


def test_cross_auction_withdrawal_independence(
    auction_house, payment_token, alice, bob, auction_struct
):
    """Test that withdrawals from one auction don't affect others"""
    # Setup two auctions
    reserve_price = auction_house.default_reserve_price()
    bid_amount1 = reserve_price
    bid_amount2 = reserve_price * 2
    outbid_amount1 = bid_amount1 * 2
    outbid_amount2 = bid_amount2 * 2

    auction_id1, _ = setup_auction_with_outbid(
        auction_house, payment_token, alice, bob, bid_amount1, outbid_amount1, auction_struct
    )

    auction_id2, _ = setup_auction_with_outbid(
        auction_house, payment_token, alice, bob, bid_amount2, outbid_amount2, auction_struct
    )

    # Withdraw from first auction
    with boa.env.prank(alice):
        auction_house.settle_auction(auction_id1)
        auction_house.withdraw(auction_id1)

    # Verify second auction's pending returns unaffected
    assert auction_house.auction_pending_returns(auction_id2, alice) > 0


def test_unauthorized_withdrawal_prevention(
    auction_house, payment_token, alice, bob, charlie, auction_struct
):
    """Test that unauthorized withdrawals are prevented"""
    reserve_price = auction_house.default_reserve_price()
    bid_amount = reserve_price
    outbid_amount = bid_amount * 2

    auction_id, _ = setup_auction_with_outbid(
        auction_house, payment_token, alice, bob, bid_amount, outbid_amount, auction_struct
    )

    # Attempt unauthorized withdrawal
    with boa.env.prank(charlie):
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id, alice)


def test_zero_pending_returns(auction_house, payment_token, alice):
    """Test withdrawal behavior with zero pending returns"""
    owner = auction_house.owner()

    # Create auction
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Attempt withdrawal without any bids
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw(auction_id)


def test_withdrawal_from_nonexistent_auction(auction_house, alice):
    """Test withdrawal attempts from non-existent auctions"""
    non_existent_id = 999

    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw(non_existent_id)


def test_empty_withdrawal_array(auction_house, alice):
    """Test withdrawal_multiple with empty array"""
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw_multiple([])


def test_max_withdrawals_limit(auction_house, payment_token, alice, bob, auction_struct):
    """Test behavior at MAX_WITHDRAWALS limit"""
    MAX_WITHDRAWALS = 100  # From contract
    auction_ids = []

    # Setup maximum number of auctions with pending returns
    reserve_price = auction_house.default_reserve_price()
    for i in range(MAX_WITHDRAWALS + 1):
        bid_amount = reserve_price
        outbid_amount = bid_amount * 2

        auction_id, _ = setup_auction_with_outbid(
            auction_house, payment_token, alice, bob, bid_amount, outbid_amount, auction_struct
        )
        auction_ids.append(auction_id)
        auction_house.settle_auction(auction_id)

    # Attempt to withdraw from more than MAX_WITHDRAWALS auctions
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw_multiple(auction_ids)

    # Should succeed with exactly MAX_WITHDRAWALS
    with boa.env.prank(alice):
        auction_house.withdraw_multiple(auction_ids[:MAX_WITHDRAWALS])


@given(
    auction_ids=st.lists(
        st.integers(min_value=1000, max_value=9999), min_size=1, max_size=5, unique=True
    )
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=10
)
def test_invalid_withdrawal_sequences(auction_house, alice, auction_ids):
    """Property-based test for invalid withdrawal sequences"""
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.withdraw_multiple(auction_ids)
