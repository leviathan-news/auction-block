import boa
import pytest
from eth.exceptions import Revert


def test_auction_extension_near_end(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision, auction_struct
):
    """Test auction extension when bid placed near end"""
    auction_id = auction_house_with_auction.auction_id()

    # Initial bid
    bid_amount = default_reserve_price
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)

    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[auction_struct.end_time]

    # Move to near end
    time_to_end = initial_end - initial_auction[auction_struct.start_time] - 10  # 10 seconds before end
    boa.env.time_travel(seconds=int(time_to_end))

    # Calculate next bid
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    next_bid = bid_amount + (bid_amount * min_increment) // precision

    # New bid should extend
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, next_bid)
        auction_house_with_auction.create_bid(auction_id, next_bid)

    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[auction_struct.end_time] > initial_end


def test_auction_extension_not_near_end(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision, auction_struct
):
    """Test auction not extended when bid placed well before end"""
    auction_id = auction_house_with_auction.auction_id()

    # Initial bid
    bid_amount = default_reserve_price
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)

    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[auction_struct.end_time]

    # Move to middle of auction
    time_to_move = (initial_end - initial_auction[auction_struct.start_time]) // 2
    boa.env.time_travel(seconds=int(time_to_move))

    # Calculate next bid
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    next_bid = bid_amount + (bid_amount * min_increment) // precision

    # New bid should not extend
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, next_bid)
        auction_house_with_auction.create_bid(auction_id, next_bid)

    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[auction_struct.end_time] == initial_end


def test_bid_validation_wrong_id(
    auction_house_with_auction, alice, payment_token, default_reserve_price
):
    """Test bid for non-existent auction fails"""
    wrong_id = auction_house_with_auction.auction_id() + 1

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        with boa.reverts("!auctionId"):
            auction_house_with_auction.create_bid(wrong_id, default_reserve_price)


def test_bid_validation_expired(
    auction_house_with_auction, alice, payment_token, default_reserve_price, auction_struct
):
    """Test bid after auction end fails"""
    auction_id = auction_house_with_auction.auction_id()

    # Move past auction end
    auction = auction_house_with_auction.auction_list(auction_id)
    time_to_end = auction[auction_struct.end_time] - auction[auction_struct.start_time] + 1
    boa.env.time_travel(seconds=int(time_to_end))

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        with boa.reverts("expired"):
            auction_house_with_auction.create_bid(auction_id, default_reserve_price)


def test_bid_validation_too_low(
    auction_house_with_auction, alice, payment_token, default_reserve_price
):
    """Test bid below reserve price fails"""
    auction_id = auction_house_with_auction.auction_id()
    low_bid = default_reserve_price - 1

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, low_bid)
        with boa.reverts("!reservePrice"):
            auction_house_with_auction.create_bid(auction_id, low_bid)


def test_bid_increment_validation(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision, auction_struct
):
    """Test minimum bid increment enforcement"""
    auction_id = auction_house_with_auction.auction_id()

    # Initial bid at reserve price
    bid_amount = default_reserve_price
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)

    # Try to bid just slightly higher
    insufficient_increment = bid_amount + 1
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, insufficient_increment)
        with boa.reverts("!increment"):
            auction_house_with_auction.create_bid(auction_id, insufficient_increment)

    # Calculate minimum valid next bid
    min_increment = (
        bid_amount * auction_house_with_auction.default_min_bid_increment_percentage()
    ) // precision
    min_next_bid = bid_amount + min_increment

    # Valid bid at minimum increment
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, min_next_bid)
        auction_house_with_auction.create_bid(auction_id, min_next_bid)

    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[auction_struct.bidder] == bob
    assert final_auction[auction_struct.amount] == min_next_bid


def test_recover_erc20(auction_house, payment_token, alice, deployer):
    """Test recovery of ERC20 tokens accidentally sent to contract"""
    # Amount to recover
    amount = 1000 * 10**18

    # Send tokens directly to contract (simulating an accident)
    with boa.env.prank(alice):
        payment_token.transfer(auction_house.address, amount)

    initial_deployer_balance = payment_token.balanceOf(deployer)

    # Only owner should be able to recover
    with boa.env.prank(alice):
        with boa.reverts():  # Non-owner call should revert
            auction_house.recover_erc20(payment_token.address, amount)

    # Owner recovers tokens
    with boa.env.prank(deployer):
        auction_house.recover_erc20(payment_token.address, amount)

    # Verify tokens were recovered
    assert payment_token.balanceOf(deployer) == initial_deployer_balance + amount
    assert payment_token.balanceOf(auction_house.address) == 0


def test_directory_recover_erc20(directory, payment_token, alice):
    """Test recovery of ERC20 tokens accidentally sent to contract"""
    # Amount to recover
    amount = 1000 * 10**18

    # Send tokens directly to contract (simulating an accident)
    with boa.env.prank(alice):
        payment_token.transfer(directory.address, amount)

    owner = directory.owner()
    initial_owner_balance = payment_token.balanceOf(owner)

    # Only owner should be able to recover
    with boa.env.prank(alice):
        with boa.reverts():  # Non-owner call should revert
            directory.recover_erc20(payment_token.address, amount)

    # Owner recovers tokens
    with boa.env.prank(owner):
        directory.recover_erc20(payment_token.address, amount)

    # Verify tokens were recovered
    assert payment_token.balanceOf(owner) == initial_owner_balance + amount
    assert payment_token.balanceOf(directory.address) == 0


def test_zap_recover_erc20(mock_trader, payment_token, alice):
    """Test recovery of ERC20 tokens accidentally sent to contract"""
    # Amount to recover
    amount = 1000 * 10**18

    # Send tokens directly to contract (simulating an accident)
    with boa.env.prank(alice):
        payment_token.transfer(mock_trader.address, amount)

    owner = mock_trader.owner()
    initial_owner_balance = payment_token.balanceOf(owner)

    # Only owner should be able to recover
    with boa.env.prank(alice):
        with boa.reverts():  # Non-owner call should revert
            mock_trader.recover_erc20(payment_token.address, amount)

    # Owner recovers tokens
    with boa.env.prank(owner):
        mock_trader.recover_erc20(payment_token.address, amount)

    # Verify tokens were recovered
    assert payment_token.balanceOf(owner) == initial_owner_balance + amount
    assert payment_token.balanceOf(mock_trader.address) == 0


def test_cannot_recover_active_auction_funds(
    auction_house_with_auction, payment_token, alice, deployer, default_reserve_price
):
    """Test that payment token recovery protects active auction funds"""
    # Place a bid first
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(1, default_reserve_price)

    # Try to recover the full balance (should fail)
    with boa.env.prank(deployer):
        with boa.reverts("cannot recover auction funds"):
            auction_house_with_auction.recover_erc20(
                payment_token.address, payment_token.balanceOf(auction_house_with_auction.address)
            )

    # Send additional tokens to contract
    excess_amount = default_reserve_price
    with boa.env.prank(alice):
        payment_token.transfer(auction_house_with_auction.address, excess_amount)

    # Should be able to recover only the excess
    initial_balance = payment_token.balanceOf(auction_house_with_auction.address)
    with boa.env.prank(deployer):
        auction_house_with_auction.recover_erc20(payment_token.address, excess_amount)

    # Verify only excess was recovered
    assert (
        payment_token.balanceOf(auction_house_with_auction.address)
        == initial_balance - excess_amount
    )
    assert payment_token.balanceOf(auction_house_with_auction.address) >= default_reserve_price


def test_cannot_receive_eth(auction_house, alice):
    """Test that the contract cannot receive ETH"""
    boa.env.set_balance(alice, 10**18)
    assert boa.env.get_balance(alice) > 0
    with pytest.raises(Revert):
        # Try to send ETH to contract using raw_call
        boa.env.raw_call(auction_house.address, sender=alice, value=1)
