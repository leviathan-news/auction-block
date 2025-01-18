import boa
import pytest


def test_set_owner(auction_house, deployer, alice):
    """Test owner can be changed by current owner"""
    with boa.env.prank(deployer):
        auction_house.set_owner(alice)
    assert auction_house.owner() == alice


def test_set_owner_zero_address(auction_house, deployer):
    """Test owner cannot be set to zero address"""
    with boa.env.prank(deployer), boa.reverts("Cannot set owner to zero address"):
        auction_house.set_owner("0x0000000000000000000000000000000000000000")
    assert auction_house.owner() == deployer


def test_set_time_buffer(auction_house, deployer):
    """Test time buffer can be updated by owner"""
    with boa.env.prank(deployer):
        auction_house.set_time_buffer(200)
    assert auction_house.time_buffer() == 200


def test_set_reserve_price(auction_house, deployer):
    """Test reserve price can be updated by owner"""
    with boa.env.prank(deployer):
        auction_house.set_reserve_price(200)
    assert auction_house.reserve_price() == 200


def test_set_min_bid_increment_percentage(auction_house, deployer, default_min_bid_increment):
    """Test minimum bid increment can be updated by owner within valid range"""
    with boa.env.prank(deployer):
        auction_house.set_min_bid_increment_percentage(10)
    assert auction_house.min_bid_increment_percentage() == 10


def test_set_min_bid_increment_percentage_too_high(
    auction_house, deployer, default_min_bid_increment
):
    """Test minimum bid increment cannot be set above maximum"""
    with boa.env.prank(deployer), boa.reverts("_min_bid_increment_percentage out of range"):
        auction_house.set_min_bid_increment_percentage(16)
    assert auction_house.min_bid_increment_percentage() == default_min_bid_increment


def test_set_min_bid_increment_percentage_too_low(
    auction_house, deployer, default_min_bid_increment
):
    """Test minimum bid increment cannot be set below minimum"""
    with boa.env.prank(deployer), boa.reverts("_min_bid_increment_percentage out of range"):
        auction_house.set_min_bid_increment_percentage(1)
    assert auction_house.min_bid_increment_percentage() == default_min_bid_increment


def test_set_duration(auction_house, deployer):
    """Test duration can be updated by owner within valid range"""
    with boa.env.prank(deployer):
        auction_house.set_duration(7200)  # 2 hours
    assert auction_house.duration() == 7200


def test_set_duration_too_short(auction_house, deployer):
    """Test duration cannot be set below minimum"""
    with boa.env.prank(deployer), boa.reverts("_duration out of range"):
        auction_house.set_duration(3599)  # Just under 1 hour
    assert auction_house.duration() == 3600


def test_set_duration_too_long(auction_house, deployer):
    """Test duration cannot be set above maximum"""
    with boa.env.prank(deployer), boa.reverts("_duration out of range"):
        auction_house.set_duration(259201)  # Just over max
    assert auction_house.duration() == 3600


def test_non_owner_cannot_set_parameters(auction_house, alice):
    """Test non-owner cannot update contract parameters"""
    with boa.env.prank(alice), boa.reverts("Caller is not the owner"):
        auction_house.set_time_buffer(200)

    with boa.env.prank(alice), boa.reverts("Caller is not the owner"):
        auction_house.set_reserve_price(200)

    with boa.env.prank(alice), boa.reverts("Caller is not the owner"):
        auction_house.set_min_bid_increment_percentage(10)

    with boa.env.prank(alice), boa.reverts("Caller is not the owner"):
        auction_house.set_duration(7200)

    with boa.env.prank(alice), boa.reverts("Caller is not the owner"):
        auction_house.set_owner(alice)


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
    with boa.env.prank(alice), boa.reverts("Caller is not the owner"):
        auction_house.pause()

    with boa.env.prank(alice), boa.reverts("Caller is not the owner"):
        auction_house.unpause()
