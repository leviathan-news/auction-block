import pytest
import boa

pytestmark = pytest.mark.fork_only

def test_pool_exists(trading_pool, auction_house, pool_indices, payment_token):
    weth_index = pool_indices[0]
    squid_index = pool_indices[1]
    reserve = auction_house.reserve_price()

    assert trading_pool.totalSupply() > 0
    assert trading_pool.coins(squid_index) == payment_token.address

    # If we're trading expensive weth to cheap SQUID, we should get more SQUID
    # Update this when SQUID flippens ETH
    assert trading_pool.get_dy(weth_index, squid_index, reserve) > reserve 

def test_weth_trader_fetches_rate(auction_house, weth_trader):
    reserve = auction_house.reserve_price()
    assert weth_trader.get_dy(reserve) > reserve 

def test_exchange(auction_house, weth_trader, weth, payment_token, alice):
    reserve = auction_house.reserve_price()
    expected = weth_trader.get_dy(reserve)
    
    init_weth = weth.balanceOf(alice)
    init_squid = payment_token.balanceOf(alice)

    with boa.env.prank(alice):
        weth.approve(weth_trader, 2 ** 256 -1)
        weth_trader.exchange(reserve, expected)
    
    assert weth.balanceOf(alice) < init_weth
    assert payment_token.balanceOf(alice) == init_squid + expected
