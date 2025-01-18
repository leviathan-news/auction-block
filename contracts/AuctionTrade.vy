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
    _indices: uint256[2],
):
    self.payment_token = _payment_token
    self.trading_token = _trading_token
    self.pool = _pool
    self.indices = _indices


@external
def exchange(
    _dx: uint256, _min_dy: uint256, _from: address = msg.sender
) -> uint256:
    """
    @notice Exchange tokens through the pool
    @param _dx Amount of trading token to exchange
    @param _min_dy Minimum amount of payment token to receive
    @param _from Optional address to pull tokens from
    @return Amount of payment token received
    """
    # Transfer tokens from sender to this contract
    extcall self.trading_token.transferFrom(_from, self, _dx)

    # Do the exchange
    extcall self.trading_token.approve(self.pool.address, max_value(uint256))
    received: uint256 = extcall self.pool.exchange(
        self.indices[0], self.indices[1], _dx, _min_dy
    )

    # Transfer output tokens back to sender
    extcall self.payment_token.transfer(_from, received)
    return received


@external
@view
def get_dy(_dx: uint256) -> uint256:
    return self._get_dy(_dx)


@internal
@view
def _get_dy(_dx: uint256) -> uint256:
    return staticcall self.pool.get_dy(self.indices[0], self.indices[1], _dx)
