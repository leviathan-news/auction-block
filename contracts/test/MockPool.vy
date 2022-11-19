# @version 0.4.0

"""
@title Mock Pool
@notice Simple mock pool for testing
"""

from ethereum.ercs import IERC20

coins: public(HashMap[uint256, address])
supply: public(uint256)
rate: public(uint256)  # Fixed rate multiplier (1e18 based)


@deploy
def __init__():
    self.supply = 1000 * 10**18
    self.rate = 2 * 10**18  # 1 token = 2 tokens fixed rate


@external
def set_coin(index: uint256, coin: address):
    self.coins[index] = coin


@external
@view
def get_dy(i: uint256, j: uint256, dx: uint256) -> uint256:
    """Mock exchange rate calculation"""
    return self._get_dy(i, j, dx)


@external
@view
def get_dx(i: uint256, j: uint256, dy: uint256) -> uint256:
    return self._get_dx(i, j, dy)


@internal
@view
def _get_dx(i: uint256, j: uint256, dy: uint256) -> uint256:
    """Reverse rate calculation"""
    return (dy * 10**18) // self.rate


@internal
@view
def _get_dy(i: uint256, j: uint256, dx: uint256) -> uint256:
    return (dx * self.rate) // 10**18


@external
def exchange(i: uint256, j: uint256, dx: uint256, min_dy: uint256) -> uint256:
    """Mock exchange"""
    input_token: IERC20 = IERC20(self.coins[i])
    output_token: IERC20 = IERC20(self.coins[j])

    dy: uint256 = self._get_dy(i, j, dx)
    assert dy >= min_dy, "slippage"

    assert extcall input_token.transferFrom(msg.sender, self, dx)
    assert extcall output_token.transfer(msg.sender, dy)

    return dy


@external
def totalSupply() -> uint256:
    return self.supply


@external
def set_rate(new_rate: uint256):
    """Allow changing the rate for testing different scenarios"""
    self.rate = new_rate


@external
def price_oracle() -> uint256:
    return 1321723924402
