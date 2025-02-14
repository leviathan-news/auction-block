import boa
import pytest


def test_set_fee_receiver(auction_house, deployer):
    """Test setting a new fee receiver address"""
    new_receiver = boa.env.generate_address()

    # Only owner should be able to set fee receiver
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts():  # Non-owner should fail
            auction_house.set_fee_receiver(new_receiver)

    # Owner should be able to set fee receiver
    with boa.env.prank(deployer):
        auction_house.set_fee_receiver(new_receiver)

    assert auction_house.fee_receiver() == new_receiver

    # Should not allow setting to zero address
    with boa.env.prank(deployer):
        with boa.reverts("!fee_receiver"):
            auction_house.set_fee_receiver("0x0000000000000000000000000000000000000000")


def test_set_fee(auction_house, deployer):
    """Test setting new fee percentages"""
    # Only owner should be able to set fee
    with boa.env.prank(boa.env.generate_address()):
        with boa.reverts():  # Non-owner should fail
            auction_house.set_fee(3)

    # Test valid fee changes
    test_fees = [0, 50, 100]  # 0%, 50%, 100%

    for new_fee in test_fees:
        with boa.env.prank(deployer):
            auction_house.set_fee(new_fee)
        assert auction_house.fee() == new_fee

    # Should not allow setting fee above MAX_FEE (100)
    with boa.env.prank(deployer):
        with boa.reverts("!fee"):
            auction_house.set_fee(101)


def test_fee_collection(
    auction_house_with_auction, deployer, alice, payment_token, default_reserve_price
):
    """Test that fees are properly collected during auction settlement"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Set fee to 10%
    test_fee = 10
    with boa.env.prank(deployer):
        house.set_fee(test_fee)

    # Place a bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    # Fast forward past auction end
    auction = house.auction_list(auction_id)
    boa.env.time_travel(seconds=int(auction[3]) - int(auction[2]) + 100)

    # Record balances before settlement
    fee_receiver = house.fee_receiver()
    fee_receiver_balance_before = payment_token.balanceOf(fee_receiver)
    owner_balance_before = payment_token.balanceOf(deployer)

    # Settle the auction
    with boa.env.prank(deployer):
        house.settle_auction(auction_id)

    # Verify fee distribution
    expected_fee = default_reserve_price * test_fee // 100
    expected_remaining = default_reserve_price - expected_fee

    fee_receiver_balance_after = payment_token.balanceOf(fee_receiver)
    owner_balance_after = payment_token.balanceOf(deployer)

    assert (
        fee_receiver_balance_after - fee_receiver_balance_before == expected_fee
    ), "Fee receiver should receive correct fee amount"
    assert (
        owner_balance_after - owner_balance_before == expected_remaining
    ), "Owner should receive remaining amount"


def test_zero_fee_settlement(
    auction_house_with_auction, deployer, alice, payment_token, default_reserve_price
):
    """Test auction settlement with 0% fee"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Set fee to 0%
    with boa.env.prank(deployer):
        house.set_fee(0)

    # Place a bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    # Fast forward past auction end
    auction = house.auction_list(auction_id)
    boa.env.time_travel(seconds=int(auction[3]) - int(auction[2]) + 100)

    # Record balances before settlement
    fee_receiver = house.fee_receiver()
    fee_receiver_balance_before = payment_token.balanceOf(fee_receiver)
    owner_balance_before = payment_token.balanceOf(deployer)

    # Settle the auction
    with boa.env.prank(deployer):
        house.settle_auction(auction_id)

    # Verify all funds go to owner
    fee_receiver_balance_after = payment_token.balanceOf(fee_receiver)
    owner_balance_after = payment_token.balanceOf(deployer)

    assert (
        fee_receiver_balance_after == fee_receiver_balance_before
    ), "Fee receiver should receive nothing"
    assert (
        owner_balance_after - owner_balance_before == default_reserve_price
    ), "Owner should receive full amount"
