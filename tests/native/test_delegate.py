import boa
import pytest


# Update the test functions to use numeric values
@pytest.fixture(scope="session")
def bid_flag():
    return 8


@pytest.fixture(scope="function")
def admin():
    """Admin wallet that will be authorized to bid on behalf of others"""
    return boa.env.generate_address()


def test_set_delegated_bidder(auction_house, deployer, admin, alice):
    """Test setting and removing delegated bidder permissions"""
    # Users can approve their own callers
    with boa.env.prank(alice):
        # No approval initially
        assert auction_house.approved_caller(alice, admin) == 0

        # Set BidOnly approval
        auction_house.set_approved_caller(admin, 1)
        assert auction_house.approved_caller(alice, admin) == 1


def test_delegated_bid_after_revocation(
    auction_house_with_auction, admin, alice, payment_token, default_reserve_price
):
    """Test revoked bidder cannot bid"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(alice):
        house.set_approved_caller(admin, 1)
        house.set_approved_caller(admin, 0)  # Revoke
        payment_token.approve(house.address, default_reserve_price * 2)

    with boa.env.prank(admin), boa.reverts("!caller"):
        house.create_bid(auction_id, default_reserve_price, "", alice)


def test_unauthorized_delegated_bid(
    auction_house_with_auction, admin, alice, bob, payment_token, default_reserve_price
):
    """Test unauthorized bidding fails"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 2)

    with boa.env.prank(bob), boa.reverts("!caller"):
        house.create_bid(auction_id, default_reserve_price, "", alice)


def test_delegated_bid(
    auction_house_with_auction, admin, alice, payment_token, default_reserve_price, bid_flag
):
    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(alice):
        # Use numeric value (1) for BidOnly
        house.set_approved_caller(admin, bid_flag)
        payment_token.approve(house.address, default_reserve_price * 2)

    with boa.env.prank(admin):
        house.create_bid(auction_id, default_reserve_price, "", alice)


def test_delegated_bid_chaining(
    auction_house_with_auction, admin, alice, bob, payment_token, default_reserve_price, bid_flag
):
    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(alice):
        house.set_approved_caller(admin, bid_flag)
        payment_token.approve(house.address, default_reserve_price * 3)

    with boa.env.prank(bob):
        house.set_approved_caller(admin, bid_flag)
        payment_token.approve(house.address, default_reserve_price * 3)

    with boa.env.prank(admin):
        house.create_bid(auction_id, default_reserve_price, "", alice)


def test_delegated_bid_with_pending_returns(
    auction_house_with_auction,
    admin,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    bid_flag,
    precision,
):
    """Test delegated bidding when the user has pending returns"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(alice):
        house.set_approved_caller(admin, bid_flag)
        payment_token.approve(house.address, default_reserve_price * 3)
        house.create_bid(auction_id, default_reserve_price)

    next_bid = default_reserve_price + (
        default_reserve_price * house.default_min_bid_increment_percentage() // precision
    )
    with boa.env.prank(bob):
        payment_token.approve(house.address, next_bid * 2)
        house.create_bid(auction_id, next_bid)

    final_bid = next_bid + (next_bid * house.default_min_bid_increment_percentage() // precision)
    with boa.env.prank(admin):
        house.create_bid(auction_id, final_bid, "", alice)


def test_delegated_bid_withdrawal(
    auction_house_with_auction, admin, alice, bob, payment_token, default_reserve_price, bid_flag
):
    """Test withdrawing after delegated bids"""
    house = auction_house_with_auction

    with boa.env.prank(alice):
        house.set_approved_caller(admin, bid_flag)
        payment_token.approve(house.address, default_reserve_price * 2)
