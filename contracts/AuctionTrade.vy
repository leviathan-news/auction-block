# @version 0.4.0

# @notice Curve token trade helper for auction bot
# @author Leviathan
# @license MIT

from ethereum.ercs import IERC20

from .imports import ownable_2step as ownable

initializes: ownable


interface Pool:
    def get_dy(i: uint256, j: uint256, dx: uint256) -> uint256: view
    def get_dx(i: uint256, j: uint256, dy: uint256) -> uint256: view
    def exchange(
        i: uint256,
        j: uint256,
        dx: uint256,
        min_dy: uint256,
    ) -> uint256: nonpayable


interface AuctionBlock:
    def auction_bid_by_user(auction_id: uint256, user: address) -> uint256: view
    def create_bid(
        auction_id: uint256,
        bid_amount: uint256,
        ipfs_hash: String[46],
        on_behalf_of: address,
    ): nonpayable
    def minimum_additional_bid_for_user(
        auction_id: uint256, user: address
    ) -> uint256: view


flag ApprovalStatus:
    Nothing  # Default value, indicating no approval
    BidOnly  # Approved for bid only
    WithdrawOnly  # Approved for withdraw only
    BidAndWithdraw  # Approved for both bid and withdraw


event ApprovedCallerSet:
    account: address
    caller: address
    status: ApprovalStatus


event DirectorySet:
    directory_address: address


payment_token: public(IERC20)
trading_token: public(IERC20)
pool: public(Pool)
indices: public(uint256[2])

# User settings: user -> caller -> status
approved_caller: public(HashMap[address, HashMap[address, ApprovalStatus]])
authorized_directory: public(address)


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

    ownable.__init__()


@external
def zap(token_amount: uint256, min_dy: uint256) -> uint256:
    """
    @notice Trade misc token for payment token
    @param token_amount Amount of misc token to swap
    @param min_dy Minimum payment tokens to receive
    @return Amount of payment tokens received
    """
    amount_received: uint256 = self._exchange(token_amount, min_dy, msg.sender)
    extcall self.payment_token.transfer(msg.sender, amount_received)
    return amount_received


@external
def zap_and_bid(
    auction_contract: AuctionBlock,
    auction_id: uint256,
    token_amount: uint256,
    min_total_bid: uint256,
    ipfs_hash: String[46] = "",
    on_behalf_of: address = msg.sender,
):
    """
    @notice Create a bid using an alternative token
    @dev Must have approved the token for use with this contract
    @param auction_id An active auction
    @param token_amount Quantity of misc token to trade.  Value should exclude any existing bid amount
    @param min_total_bid Required minimum final total bid value, or revert (slippage)
    @param on_behalf_of User to bid on behalf of
    @param ipfs_hash Optional data to register with the bid
    """
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    current_bid: uint256 = staticcall auction_contract.auction_bid_by_user(
        auction_id, on_behalf_of
    )
    tokens_needed: uint256 = (
        staticcall auction_contract.minimum_additional_bid_for_user(
            auction_id, on_behalf_of
        )
    )

    dy: uint256 = self._get_dy(token_amount)
    assert dy >= tokens_needed, "!token_amount"
    assert dy + current_bid >= min_total_bid, "!token_amount"

    token_source: address = on_behalf_of
    if msg.sender == self.authorized_directory:
        token_source = self.authorized_directory

    amount_received: uint256 = self._exchange(token_amount, dy, token_source)

    total_bid: uint256 = amount_received + current_bid
    assert total_bid >= min_total_bid, "!token_amount"

    extcall self.payment_token.transfer(msg.sender, amount_received)
    extcall auction_contract.create_bid(
        auction_id, total_bid, ipfs_hash, on_behalf_of
    )


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
    received: uint256 = self._exchange(_dx, _min_dy, _from)
    # Transfer output tokens back to sender
    extcall self.payment_token.transfer(_from, received)
    return received


@internal
def _exchange(
    _dx: uint256, _min_dy: uint256, _from: address = msg.sender
) -> uint256:
    # Transfer tokens from sender to this contract
    extcall self.trading_token.transferFrom(_from, self, _dx)

    # Do the exchange
    extcall self.trading_token.approve(self.pool.address, max_value(uint256))
    received: uint256 = extcall self.pool.exchange(
        self.indices[0], self.indices[1], _dx, _min_dy
    )
    return received


@external
@view
def get_dx(_dy: uint256) -> uint256:
    return self._get_dx(_dy)


@external
@view
def get_dy(_dx: uint256) -> uint256:
    return self._get_dy(_dx)


@external
@view
def safe_get_dx(_dy: uint256) -> uint256:
    """
    @dev A gas fuzzling function, recommend not to use in smart contracts
    @return A safe dx above the minimum required to guarantee dy
    """
    _actual_dy: uint256 = 0
    _dx: uint256 = self._get_dx(_dy)
    for _i: uint256 in range(10):
        _actual_dy = self._get_dy(_dx)
        if _actual_dy >= _dy:
            break
        else:
            _dx = _dx * 100000001 // 100000000
    assert _actual_dy >= _dy
    return _dx


@external
def set_approved_caller(caller: address, status: ApprovalStatus):
    """
    @dev Set approval status for a caller
    """
    self.approved_caller[msg.sender][caller] = status
    log ApprovedCallerSet(msg.sender, caller, status)


@external
def set_approved_directory(directory_address: address):
    """
    @dev Authorized directory contract with permissions
    """
    ownable._check_owner()
    self.authorized_directory = directory_address
    log DirectorySet(directory_address)


@internal
@view
def _get_dx(_dy: uint256) -> uint256:
    return staticcall self.pool.get_dx(self.indices[0], self.indices[1], _dy)


@internal
@view
def _get_dy(_dx: uint256) -> uint256:
    return staticcall self.pool.get_dy(self.indices[0], self.indices[1], _dx)


@internal
@view
def _check_caller(
    _account: address, _caller: address, _req_status: ApprovalStatus
):
    # Directory contract assumes onus of confirming status
    if _account != _caller and msg.sender != self.authorized_directory:
        _status: ApprovalStatus = self.approved_caller[_account][_caller]
        if _status == ApprovalStatus.BidAndWithdraw:
            return
        assert (_status == _req_status), "!caller"
