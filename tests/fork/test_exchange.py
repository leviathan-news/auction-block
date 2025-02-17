import boa
import pytest

pytestmark = pytest.mark.fork_only


def test_pool_exists(trading_pool, auction_house, pool_indices, payment_token):
    weth_index = pool_indices[0]
    squid_index = pool_indices[1]
    reserve = auction_house.default_reserve_price()

    assert trading_pool.totalSupply() > 0
    assert trading_pool.coins(squid_index) == payment_token.address

    # If we're trading expensive weth to cheap SQUID, we should get more SQUID
    # Update this when SQUID flippens ETH
    assert trading_pool.get_dy(weth_index, squid_index, reserve) > reserve


def test_weth_trader_fetches_rate(auction_house, weth_trader):
    reserve = auction_house.default_reserve_price()
    assert weth_trader.get_dy(reserve) > reserve


def test_exchange(auction_house, weth_trader, weth, payment_token, alice):
    reserve = auction_house.default_reserve_price()
    expected = weth_trader.get_dy(reserve)

    init_weth = weth.balanceOf(alice)
    init_squid = payment_token.balanceOf(alice)

    with boa.env.prank(alice):
        weth.approve(weth_trader, 2**256 - 1)
        weth_trader.exchange(reserve, expected)

    assert weth.balanceOf(alice) < init_weth
    assert payment_token.balanceOf(alice) == init_squid + expected


def test_bid_with_misc_token(
    auction_house, weth_trader, weth, payment_token, alice, approval_flags
):
    owner = auction_house.owner()

    # Setup auction and unpause as owner
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Get required bid amount
    min_bid = auction_house.minimum_total_bid(auction_id)
    expected_payment = weth_trader.get_dy(min_bid)

    # Record initial balances
    init_weth = weth.balanceOf(alice)
    assert init_weth >= min_bid, "Alice should have enough WETH from fixture"
    init_squid = payment_token.balanceOf(alice)

    # Place bid with WETH
    with boa.env.prank(alice):
        weth.approve(weth_trader.address, 2**256 - 1)
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(weth_trader, approval_flags.BidOnly)

        weth_trader.zap_and_bid(auction_house, auction_id, min_bid, expected_payment)

    # Verify WETH was spent
    assert weth.balanceOf(alice) < init_weth
    assert payment_token.balanceOf(alice) == init_squid

    # Verify bid was placed correctly
    auction = auction_house.auction_list(auction_id)
    assert auction[4] == alice
    assert auction[1] == expected_payment


def test_bid_with_misc_token_reverts_on_bad_slippage(
    auction_house, weth_trader, weth, alice, approval_flags, payment_token
):
    owner = auction_house.owner()

    # Setup auction and unpause as owner
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Get required bid amount
    min_bid = auction_house.minimum_total_bid(auction_id)
    expected_payment = weth_trader.get_dy(min_bid)

    # Try to place bid with unrealistic min_amount_out
    with boa.env.prank(alice):
        weth.approve(weth_trader, 2**256 - 1)  # Approve trader instead of auction house
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(weth_trader, approval_flags.BidOnly)

        with pytest.raises(Exception):  # Should revert
            weth_trader.zap_and_bid(
                auction_house,
                auction_id,
                min_bid,
                expected_payment * 2,  # Unrealistic slippage protection
            )


def test_bid_with_misc_token_reverts_on_unsupported_token(auction_house, weth, alice):
    owner = auction_house.owner()

    # Setup auction and unpause as owner
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Get required bid amount
    min_bid = auction_house.minimum_total_bid(auction_id)

    # Try to bid with unsupported token
    with boa.env.prank(alice):
        weth.approve(auction_house, 2**256 - 1)
        with pytest.raises(Exception):
            auction_house.create_bid_with_token(auction_id, min_bid, weth, min_bid)
