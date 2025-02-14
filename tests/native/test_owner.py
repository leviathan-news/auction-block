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


def test_set_default_time_buffer(auction_house, deployer):
    """Test time buffer can be updated by owner"""
    with boa.env.prank(deployer):
        auction_house.set_default_time_buffer(200)
    assert auction_house.default_time_buffer() == 200


def test_set_default_reserve_price(auction_house, deployer):
    """Test reserve price can be updated by owner"""
    with boa.env.prank(deployer):
        auction_house.set_default_reserve_price(200)
    assert auction_house.default_reserve_price() == 200


def test_set_default_min_bid_increment_percentage(
    auction_house, deployer, default_min_bid_increment
):
    """Test minimum bid increment can be updated by owner within valid range"""
    with boa.env.prank(deployer):
        auction_house.set_default_min_bid_increment_percentage(10)
    assert auction_house.default_min_bid_increment_percentage() == 10


@pytest.mark.skip()
def test_set_default_min_bid_increment_percentage_too_high(
    auction_house, deployer, default_min_bid_increment
):
    """Test minimum bid increment cannot be set above maximum"""
    with boa.env.prank(deployer), boa.reverts("!percentage"):
        auction_house.set_default_min_bid_increment_percentage(99999999)
    assert auction_house.default_min_bid_increment_percentage() == default_min_bid_increment


@pytest.mark.skip()
def test_set_default_min_bid_increment_percentage_too_low(
    auction_house, deployer, default_min_bid_increment
):
    """Test minimum bid increment cannot be set below minimum"""
    with boa.env.prank(deployer), boa.reverts("!percentage"):
        auction_house.set_default_min_bid_increment_percentage(0)
    assert auction_house.default_min_bid_increment_percentage() == default_min_bid_increment


def test_set_default_duration(auction_house, deployer):
    """Test duration can be updated by owner within valid range"""
    with boa.env.prank(deployer):
        auction_house.set_default_duration(7200)  # 2 hours
    assert auction_house.default_duration() == 7200


@pytest.mark.skip()
def test_set_default_duration_too_short(auction_house, deployer):
    """Test duration cannot be set below minimum"""
    with boa.env.prank(deployer), boa.reverts("!duration"):
        auction_house.set_default_duration(3599)  # Just under 1 hour
    assert auction_house.default_duration() == 3600


@pytest.mark.skip()
def test_set_default_duration_too_long(auction_house, deployer):
    """Test duration cannot be set above maximum"""
    with boa.env.prank(deployer), boa.reverts("!duration"):
        auction_house.set_default_duration(259201)  # Just over max
    assert auction_house.default_duration() == 3600


def test_non_owner_cannot_set_default_parameters(auction_house, alice):
    """Test non-owner cannot update parameters"""
    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.set_default_time_buffer(200)

    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.set_default_reserve_price(200)

    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.set_default_min_bid_increment_percentage(10)

    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.set_default_duration(7200)

    with boa.env.prank(alice), boa.reverts("!owner"):
        auction_house.transfer_ownership(alice)  # Uses 2-step ownership transfer


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
