# @version 0.4.0

# @notice Curve token trade helper for auction bot
# @author Leviathan
# @license MIT

from ethereum.ercs import IERC20

interface Pool:
    def get_dy(i: uint256, j: uint256, dx: uint256) -> uint256: view
    def exchange(
        i: uint256,
        j: uint256,
        dx: uint256,
        min_dy: uint256,
    ) -> uint256: nonpayable

payment_token: public(IERC20)
trading_token: public(IERC20)
pool: public(Pool)
indices: public(uint256[2])


@deploy
def __init__(
    _payment_token: IERC20,
    _trading_token: IERC20,
    _pool: Pool,
    _indices: uint256[2]
):
    self.payment_token = _payment_token
    self.trading_token = _trading_token
    self.pool = _pool
    self.indices = _indices

@external
def exchange(_dx: uint256, _min_dy: uint256) -> uint256:
    extcall self.trading_token.transferFrom(msg.sender, self, _dx)
    extcall self.trading_token.approve(self.pool.address, max_value(uint256))
    amount: uint256 = extcall self.pool.exchange(self.indices[0], self.indices[1], _dx, _min_dy)
    extcall self.payment_token.transfer(msg.sender, amount)
    return amount
 
@external
@view
def get_dy(_dx: uint256) -> uint256:
    return self._get_dy(_dx) 

@internal
@view
def _get_dy(_dx: uint256) -> uint256:
    return staticcall self.pool.get_dy(self.indices[0], self.indices[1], _dx)

   
