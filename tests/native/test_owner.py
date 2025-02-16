import boa
import pytest


def test_non_owner_cannot_create_auction(auction_house, alice):
    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.create_new_auction()


def test_set_owner(auction_house, deployer, alice):
    """Test owner can be changed by current owner"""
    with boa.env.prank(deployer):
        auction_house.transfer_ownership(alice)
    with boa.env.prank(alice):
        auction_house.accept_ownership()
    assert auction_house.owner() == alice


def test_set_owner_zero_address(auction_house, deployer):
    """Test owner can transfer to zero address but it cannot accept"""
    with boa.env.prank(deployer):
        auction_house.transfer_ownership("0x0000000000000000000000000000000000000000")


def test_non_owner_cannot_transfer(auction_house, alice):
    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.transfer_ownership(alice)  # Uses 2-step ownership transfer

    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.pause()  # Uses 2-step ownership transfer


def test_pause_unpause(auction_house_with_auction, deployer):
    """Test pausing and unpausing by owner"""
    assert not auction_house_with_auction.paused()

    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
    assert auction_house_with_auction.paused()

    with boa.env.prank(deployer):
        auction_house_with_auction.unpause()
    assert not auction_house_with_auction.paused()


def test_non_owner_cannot_pause_unpause(auction_house, alice):
    """Test non-owner cannot pause or unpause"""
    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.pause()

    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.unpause()


def test_can_nullify_active_auction(
    auction_house_with_auction, alice, payment_token, deployer, zero_address
):
    house = auction_house_with_auction
    bid = house.default_reserve_price()
    auction_id = house.auction_id()
    with boa.env.prank(alice):
        payment_token.approve(house, bid)
        house.create_bid(auction_id, bid)
    assert house.auction_list(auction_id)[4] == alice
    assert house.auction_remaining_time(auction_id) > 0

    with boa.env.prank(deployer):
        house.nullify_auction(auction_id)

    auction = house.auction_list(auction_id)
    assert house.auction_remaining_time(auction_id) == 0
    assert auction[1] == 0
    assert auction[4] == zero_address
    assert auction[5] is True
    assert house.auction_pending_returns(auction_id, alice) == bid


def test_winner_can_withdraw_from_nullified_auction(
    auction_house_with_auction, alice, payment_token, deployer
):
    house = auction_house_with_auction
    bid = house.default_reserve_price()
    auction_id = house.auction_id()
    with boa.env.prank(alice):
        payment_token.approve(house, bid)
        house.create_bid(auction_id, bid)
    assert house.auction_list(auction_id)[4] == alice

    init_squid = payment_token.balanceOf(alice)
    with boa.env.prank(deployer):
        house.nullify_auction(auction_id)

    with boa.env.prank(alice):
        house.withdraw(auction_id)

    assert payment_token.balanceOf(alice) == init_squid + bid


def test_cannot_nullify_settled_auction(auction_house_with_auction, alice, payment_token, deployer):
    house = auction_house_with_auction
    bid = house.default_reserve_price()
    auction_id = house.auction_id()
    with boa.env.prank(alice):
        payment_token.approve(house, bid)
        house.create_bid(auction_id, bid)
    assert house.auction_list(auction_id)[4] == alice

    boa.env.time_travel(house.auction_remaining_time(auction_id) + 1)
    house.settle_auction(auction_id)

    # Alice cannot withdraw as winner
    init_squid = payment_token.balanceOf(alice)
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
    assert payment_token.balanceOf(alice) == init_squid

    with boa.env.prank(deployer):
        with boa.reverts("settled"):
            house.nullify_auction(auction_id)

    # Sadly, Alice cannot withdraw because it was settled before it was nullified
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)

    assert payment_token.balanceOf(alice) == init_squid


def test_can_nullify_when_paused(
    auction_house_with_auction, alice, payment_token, deployer, zero_address
):
    house = auction_house_with_auction
    bid = house.default_reserve_price()
    auction_id = house.auction_id()
    with boa.env.prank(alice):
        payment_token.approve(house, bid)
        house.create_bid(auction_id, bid)
    assert house.auction_list(auction_id)[4] == alice

    with boa.env.prank(deployer):
        house.pause()

    init_squid = payment_token.balanceOf(alice)
    with boa.env.prank(deployer):
        house.nullify_auction(auction_id)

    auction = house.auction_list(auction_id)
    assert house.auction_remaining_time(auction_id) == 0
    assert auction[1] == 0
    assert auction[4] == zero_address
    assert auction[5] is True
    assert house.auction_pending_returns(auction_id, alice) == bid

    with boa.env.prank(deployer):
        house.unpause()

    with boa.env.prank(alice):
        house.withdraw(auction_id)

    assert payment_token.balanceOf(alice) == init_squid + bid


# Pause checks
def test_cannot_settle_when_paused(auction_house_with_auction, deployer):
    """Test that settle_auction cannot be called when paused"""
    # First time travel past end time so we can settle
    remaining = auction_house_with_auction.auction_remaining_time(1)
    boa.env.time_travel(seconds=remaining + 1)

    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to settle - should fail
    with boa.reverts("paused"):
        auction_house_with_auction.settle_auction(1)


def test_cannot_create_bid_when_paused(auction_house_with_auction, alice, payment_token, deployer):
    """Test that create_bid cannot be called when paused"""
    auction_id = auction_house_with_auction.auction_id()
    bid_amount = auction_house_with_auction.default_reserve_price()

    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to create bid - should fail
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction, bid_amount)
        with boa.reverts("paused"):
            auction_house_with_auction.create_bid(auction_id, bid_amount)


# @pytest.mark.fork_only
@pytest.mark.skip()
def test_cannot_create_token_bid_when_paused(
    auction_house_with_auction, alice, payment_token, weth, deployer
):
    """Test that create_bid_with_token cannot be called when paused"""
    auction_id = auction_house_with_auction.auction_id()
    bid_amount = auction_house_with_auction.default_reserve_price()

    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to create token bid - should fail
    with boa.env.prank(alice):
        weth.approve(auction_house_with_auction, bid_amount)
        with boa.reverts("paused"):
            auction_house_with_auction.create_bid_with_token(
                auction_id, bid_amount, weth, bid_amount
            )


def test_cannot_withdraw_when_paused(auction_house_with_auction, alice, payment_token, deployer):
    """Test that withdraw cannot be called when paused"""
    # Setup: Create bid and end auction
    auction_id = auction_house_with_auction.auction_id()
    bid_amount = auction_house_with_auction.default_reserve_price()

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)

    # Time travel to end
    remaining = auction_house_with_auction.auction_remaining_time(auction_id)
    boa.env.time_travel(seconds=remaining + 1)

    # Settle auction
    auction_house_with_auction.settle_auction(auction_id)

    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to withdraw - should fail
    with boa.env.prank(alice):
        with boa.reverts("paused"):
            auction_house_with_auction.withdraw(auction_id)


def test_cannot_withdraw_multiple_when_paused(
    auction_house_with_auction, alice, payment_token, deployer
):
    """Test that withdraw_multiple cannot be called when paused"""
    # Setup: Create bid and end auction
    auction_id = auction_house_with_auction.auction_id()
    bid_amount = auction_house_with_auction.default_reserve_price()

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)

    # Time travel to end
    remaining = auction_house_with_auction.auction_remaining_time(auction_id)
    boa.env.time_travel(seconds=remaining + 1)

    # Settle auction
    auction_house_with_auction.settle_auction(auction_id)

    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to withdraw multiple - should fail
    with boa.env.prank(alice):
        with boa.reverts("paused"):
            auction_house_with_auction.withdraw_multiple([auction_id])


def test_cannot_withdraw_stale_when_paused(auction_house_with_auction, alice, deployer):
    """Test that withdraw_stale cannot be called when paused"""
    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to withdraw stale - should fail
    with boa.env.prank(deployer):
        with boa.reverts("paused"):
            auction_house_with_auction.withdraw_stale([alice])


def test_cannot_create_new_auction_when_paused(auction_house_with_auction, deployer):
    """Test that create_new_auction cannot be called when paused"""
    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to create new auction - should fail
    with boa.env.prank(deployer):
        with boa.reverts("paused"):
            auction_house_with_auction.create_new_auction()


def test_cannot_create_custom_auction_when_paused(auction_house_with_auction, deployer):
    """Test that create_custom_auction cannot be called when paused"""
    # Pause contract
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()

    # Try to create custom auction - should fail
    with boa.env.prank(deployer):
        with boa.reverts("paused"):
            auction_house_with_auction.create_custom_auction(
                300,  # time_buffer
                100,  # reserve_price
                5,  # min_bid_increment_percentage
                3600,  # duration
            )
