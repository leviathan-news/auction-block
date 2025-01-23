import boa
import pytest

pytestmark = pytest.mark.fork_only


def test_get_dy(auction_house, weth_trader, weth):
    """Test straightforward price calculation"""
    # Setup
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.add_token_support(weth, weth_trader)

    # Test price calculation matches trader
    amount = 10**18  # 1 WETH
    expected = weth_trader.get_dy(amount)
    actual = auction_house.get_dy(weth, amount)
    assert actual == expected


def test_get_dx(auction_house, weth_trader, weth):
    """Test reverse price calculation"""
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.add_token_support(weth, weth_trader)

    squid_amount = 10**18  # Amount of SQUID we want
    expected = weth_trader.get_dx(squid_amount)
    actual = auction_house.get_dx(weth, squid_amount)
    assert actual == expected


def test_safe_get_dx(auction_house, weth_trader, weth):
    """Test safe reverse calculation with slippage protection"""
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.add_token_support(weth, weth_trader)

    squid_amount = 10**18
    dx = auction_house.safe_get_dx(weth, squid_amount)

    # Verify we get at least the requested amount when using this dx
    dy = weth_trader.get_dy(dx)
    assert dy >= squid_amount

    # Should be within 0.1% of regular get_dx
    regular_dx = auction_house.get_dx(weth, squid_amount)
    assert abs(dx - regular_dx) <= regular_dx // 1000


def test_get_dy_reverts_on_unsupported_token(auction_house, weth):
    """Test get_dy fails for unsupported token"""
    with pytest.raises(Exception):
        auction_house.get_dy(weth, 10**18)


def test_get_dx_reverts_on_unsupported_token(auction_house, weth):
    """Test get_dx fails for unsupported token"""
    with pytest.raises(Exception):
        auction_house.get_dx(weth, 10**18)


def test_safe_get_dx_reverts_on_unsupported_token(auction_house, weth):
    """Test safe_get_dx fails for unsupported token"""
    with pytest.raises(Exception):
        auction_house.safe_get_dx(weth, 10**18)


def test_safe_get_dx_large_amounts(auction_house, weth_trader, weth):
    """Test safe_get_dx with larger amounts that may have more slippage"""
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.add_token_support(weth, weth_trader)

    # Test with 1000 SQUID
    large_amount = 1000 * 10**18
    dx = auction_house.safe_get_dx(weth, large_amount)
    dy = weth_trader.get_dy(dx)

    assert dy >= large_amount  # Must get at least requested amount
    # Slippage should still be reasonable
    assert dy <= large_amount * 102 // 100  # Max 2% over
