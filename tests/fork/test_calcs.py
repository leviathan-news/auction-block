import boa
import pytest

pytestmark = pytest.mark.fork_only


def test_get_dy(weth_trader, weth, directory):
    """Test straightforward price calculation"""

    # Test price calculation matches zap
    amount = 10**18  # 1 WETH
    expected = weth_trader.get_dy(amount)
    actual = directory.get_dy(weth, amount)
    assert actual == expected


def test_get_dx_returns(directory, weth_trader, weth):
    """Test reverse price calculation"""
    squid_amount = 10**18  # Amount of SQUID we want
    expected = weth_trader.get_dx(squid_amount)
    assert expected > 0


def test_safe_get_dx(directory, weth_trader, weth):
    """Test safe reverse calculation with slippage protection"""

    squid_amount = 10**18
    dx = directory.safe_get_dx(weth, squid_amount)

    # Verify we get at least the requested amount when using this dx
    dy = weth_trader.get_dy(dx)
    dy = directory.get_dy(weth, dx)
    assert dy >= squid_amount

    # Should be within 0.1% of regular get_dx
    regular_dx = weth_trader.get_dx(squid_amount)
    assert abs(dx - regular_dx) <= regular_dx // 1000


def test_get_dy_reverts_on_unsupported_token(directory):
    """Test get_dy fails for unsupported token"""
    fake_token = boa.env.generate_address()
    with boa.reverts("!token"):
        directory.get_dy(fake_token, 10**18)


def test_safe_get_dx_reverts_on_unsupported_token(directory):
    """Test safe_get_dx fails for unsupported token"""
    fake_token = boa.env.generate_address()
    with boa.reverts("!token"):
        directory.safe_get_dx(fake_token, 10**18)


def test_safe_get_dx_large_amounts(directory, weth_trader, weth):
    """Test safe_get_dx with larger amounts that may have more slippage"""

    # Test with 1000 SQUID
    large_amount = 1000 * 10**18
    dx = directory.safe_get_dx(weth, large_amount)
    dy = weth_trader.get_dy(dx)

    assert dy >= large_amount  # Must get at least requested amount
    # Slippage should still be reasonable
    assert dy <= large_amount * 102 // 100  # Max 2% over
