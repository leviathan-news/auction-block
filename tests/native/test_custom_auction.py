import boa
import pytest


def test_create_custom_auction(
    auction_house,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    default_duration,
    ipfs_hash,
    auction_params_struct,
    auction_struct
):
    """Test creating a custom auction with non-default parameters"""
    # Custom parameters different from defaults
    custom_time_buffer = default_time_buffer * 2
    custom_reserve_price = default_reserve_price * 2
    custom_min_bid_increment = default_min_bid_increment + 1
    custom_duration = default_duration * 2

    with boa.env.prank(deployer):
        auction_id = auction_house.create_custom_auction(
            custom_time_buffer,
            custom_reserve_price,
            custom_min_bid_increment,
            custom_duration,
            ipfs_hash,
        )

    # Retrieve the created auction
    auction = auction_house.auction_list(auction_id)

    # Verify auction parameters
    assert auction[auction_struct.auction_id] == auction_id, "Auction ID should match"
    assert auction[auction_struct.amount] == 0, "Initial auction amount should be 0"
    assert auction[auction_struct.start_time] > 0, "Start time should be set"
    assert (
        auction[auction_struct.end_time] == auction[auction_struct.start_time] + custom_duration
    ), "End time should be calculated from custom duration"
    assert (
        auction[auction_struct.bidder] == "0x0000000000000000000000000000000000000000"
    ), "Initial bidder should be empty"
    assert auction[auction_struct.settled] is False, "Auction should not be settled"
    assert auction[auction_struct.ipfs_hash] == ipfs_hash, "IPFS hash should match"

    # Verify auction parameters struct
    auction_params = auction[auction_struct.params]
    assert auction_params[auction_params_struct.time_buffer] == custom_time_buffer, "Time buffer should match custom value"
    assert auction_params[auction_params_struct.reserve_price] == custom_reserve_price, "Reserve price should match custom value"
    assert (
        auction_params[auction_params_struct.min_bid_increment_percentage] == custom_min_bid_increment
    ), "Min bid increment percentage should match custom value"
    assert auction_params[auction_params_struct.duration] == custom_duration, "Duration should match custom value"


def test_create_custom_auction_only_owner(
    auction_house,
    alice,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    default_duration,
):
    """Test that only the owner can create a custom auction"""
    with boa.env.prank(alice):
        with boa.reverts("!owner"):
            auction_house.create_custom_auction(
                default_time_buffer,
                default_reserve_price,
                default_min_bid_increment,
                default_duration,
                "",
            )
