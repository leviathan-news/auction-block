# @version 0.4.0

"""
@title Auction Block
@license MIT
@author Leviathan
@notice Auction block facilitates creating, bidding on, and settling auctions with multiple token support
"""

from ethereum.ercs import IERC20

import ownable_2step as ownable
import pausable


# ============================================================================================
# Interfaces
# ============================================================================================

interface TokenTrader:
    def exchange(
        _dx: uint256, _min_dy: uint256, _from: address = msg.sender
    ) -> uint256: nonpayable
    def get_dx(_dy: uint256) -> uint256: view
    def get_dy(_dx: uint256) -> uint256: view


# ============================================================================================
# Modules
# ============================================================================================

initializes: ownable
exports: (
    ownable.owner,
    ownable.pending_owner,
    ownable.transfer_ownership,
    ownable.accept_ownership,
)

initializes: pausable[ownable := ownable]
exports: (
    pausable.paused,
    pausable.pause,
    pausable.unpause,
)


# ============================================================================================
# Structs
# ============================================================================================

struct Auction:
    auction_id: uint256
    amount: uint256
    start_time: uint256
    end_time: uint256
    bidder: address
    settled: bool
    ipfs_hash: String[46]
    params: AuctionParams


struct AuctionParams:
    time_buffer: uint256
    reserve_price: uint256
    min_bid_increment_percentage: uint256
    duration: uint256


flag ApprovalStatus:
    Nothing  # Default value, indicating no approval
    BidOnly  # Approved for bid only
    WithdrawOnly  # Approved for withdraw only
    BidAndWithdraw  # Approved for both bid and withdraw


# ============================================================================================
# Events
# ============================================================================================

event AuctionBid:
    auction_id: indexed(uint256)
    bidder: indexed(address)
    caller: indexed(address)
    value: uint256
    extended: bool


event AuctionExtended:
    auction_id: indexed(uint256)
    end_time: uint256


event DefaultAuctionTimeBufferUpdated:
    default_time_buffer: uint256


event DefaultAuctionReservePriceUpdated:
    default_reserve_price: uint256


event DefaultAuctionMinBidIncrementPercentageUpdated:
    default_min_bid_increment_percentage: uint256


event DefaultAuctionDurationUpdated:
    default_duration: uint256


event AuctionCreated:
    auction_id: indexed(uint256)
    start_time: uint256
    end_time: uint256
    ipfs_hash: String[46]


event AuctionSettled:
    auction_id: indexed(uint256)
    winner: address
    amount: uint256


event Withdraw:
    auction_id: indexed(uint256)
    on_behalf_of: indexed(address)
    caller: indexed(address)
    amount: uint256


event TokenSupportAdded:
    token: indexed(address)
    trader: indexed(address)


event TokenSupportRemoved:
    token: indexed(address)


event ApprovedCallerSet:
    account: address
    caller: address
    status: ApprovalStatus


event FeeReceiverUpdated:
    fee_receiver: address


event FeeUpdated:
    fee: uint256


# ============================================================================================
# Constants
# ============================================================================================

PRECISION: constant(uint256) = 100
MAX_WITHDRAWALS: constant(uint256) = 100
MAX_TOKENS: constant(uint256) = 100
MAX_AUCTIONS: constant(uint256) = 100
MIN_DURATION: constant(uint256) = 3600  # 1 hour
MAX_DURATION: constant(uint256) = 259200  # 3 days
MIN_BID_INCREMENT_PERCENTAGE_: constant(uint256) = 2  # 2%
MAX_BID_INCREMENT_PERCENTAGE: constant(uint256) = 15  # 15%
MAX_FEE: constant(uint256) = 100  # 10%


# ============================================================================================
# Storage
# ============================================================================================

# Auction
default_time_buffer: public(uint256)
default_reserve_price: public(uint256)
default_min_bid_increment_percentage: public(uint256)
default_duration: public(uint256)
auction_id: public(uint256)

auction_pending_returns: public(HashMap[uint256, HashMap[address, uint256]])
auction_list: public(HashMap[uint256, Auction])

# User settings
approved_caller: public(HashMap[address, HashMap[address, ApprovalStatus]])

# Payment tokensr
payment_token: public(IERC20)
additional_tokens: public(HashMap[IERC20, TokenTrader])
supported_tokens: public(DynArray[IERC20, MAX_TOKENS])

# Fee configuration
fee_receiver: public(address)
fee: public(uint256)


# ============================================================================================
# Constructor
# ============================================================================================

@deploy
def __init__(
    time_buffer: uint256,
    reserve_price: uint256,
    min_bid_increment_percentage: uint256,
    duration: uint256,
    payment_token: address,
    fee_receiver: address,
    fee: uint256,
):
    assert (
        min_bid_increment_percentage >= MIN_BID_INCREMENT_PERCENTAGE_
        and min_bid_increment_percentage <= MAX_BID_INCREMENT_PERCENTAGE
    ), "!min_bid_increment_percentage"
    assert duration >= MIN_DURATION and duration <= MAX_DURATION, "!duration"
    assert payment_token != empty(address), "!payment_token"
    assert fee_receiver != empty(address), "!fee_receiver"
    assert fee <= MAX_FEE, "!fee"

    ownable.__init__()
    pausable.__init__()

    # Defaults
    self.default_time_buffer = time_buffer
    self.default_reserve_price = reserve_price
    self.default_min_bid_increment_percentage = min_bid_increment_percentage
    self.default_duration = duration

    # Money
    self.payment_token = IERC20(payment_token)
    self.fee_receiver = fee_receiver
    self.fee = fee


# ============================================================================================
# View functions
# ============================================================================================

@external
@view
def current_auctions() -> DynArray[uint256, MAX_AUCTIONS]:
    """
    @dev Returns an array of currently active auction IDs based on timestamp
    @return Array of auction IDs that are currently active (between start and end time)
    """
    active_auctions: DynArray[uint256, MAX_AUCTIONS] = []

    for i: uint256 in range(MAX_AUCTIONS):
        if i + 1 > self.auction_id:
            break

        auction: Auction = self.auction_list[i + 1]
        if (
            auction.start_time <= block.timestamp
            and block.timestamp <= auction.end_time
            and not auction.settled
        ):
            active_auctions.append(i + 1)
    return active_auctions


@internal
def _settle_auction(auction_id: uint256):
    _auction: Auction = self.auction_list[auction_id]
    assert _auction.start_time != 0, "!auction"
    assert _auction.settled == False, "settled"
    assert block.timestamp > _auction.end_time, "!completed"

    self.auction_list[auction_id] = Auction(
        auction_id=_auction.auction_id,
        amount=_auction.amount,
        start_time=_auction.start_time,
        end_time=_auction.end_time,
        bidder=_auction.bidder,
        settled=True,
        ipfs_hash=_auction.ipfs_hash,
        params=_auction.params,
    )

    if _auction.amount > 0:
        fee_amount: uint256 = _auction.amount * self.fee // PRECISION
        remaining_amount: uint256 = _auction.amount - fee_amount

        if fee_amount > 0:
            assert extcall self.payment_token.transfer(
                self.fee_receiver, fee_amount, default_return_value=True
            ), "!fee transfer"

        assert extcall self.payment_token.transfer(
            ownable.owner, remaining_amount, default_return_value=True
        ), "!owner transfer"

    log AuctionSettled(_auction.auction_id, _auction.bidder, _auction.amount)


@internal
def _collect_payment(auction_id: uint256, total_bid: uint256, bidder: address):
    tokens_needed: uint256 = total_bid
    pending_amount: uint256 = self.auction_pending_returns[auction_id][bidder]
    if pending_amount > 0:
        if pending_amount >= total_bid:
            self.auction_pending_returns[auction_id][bidder] = (
                pending_amount - total_bid
            )
            tokens_needed = 0
        else:
            self.auction_pending_returns[auction_id][bidder] = 0
            tokens_needed = total_bid - pending_amount
    if tokens_needed > 0:
        assert extcall self.payment_token.transferFrom(
            bidder, self, tokens_needed, default_return_value=True
        ), "!transfer"


@internal
def _create_bid(auction_id: uint256, total_bid: uint256, bidder: address):
    _auction: Auction = self.auction_list[auction_id]
    _time_buffer: uint256 = _auction.params.time_buffer
    _reserve_price: uint256 = _auction.params.reserve_price

    assert _auction.auction_id == auction_id, "!auctionId"
    assert block.timestamp < _auction.end_time, "expired"
    assert total_bid >= _reserve_price, "!reservePrice"
    assert total_bid >= self._minimum_total_bid(auction_id), "!increment"

    last_bidder: address = _auction.bidder
    if last_bidder != empty(address):
        self.auction_pending_returns[auction_id][last_bidder] += _auction.amount
   
    # Exctend the auction?
    _end_time: uint256 = _auction.end_time

    _extended: bool = _auction.end_time - block.timestamp < _time_buffer
    if _extended:
        _end_time = block.timestamp + _time_buffer

    self.auction_list[auction_id] = Auction(
        auction_id=_auction.auction_id,
        amount=total_bid,
        start_time=_auction.start_time,
        end_time = _end_time,
        bidder=bidder,
        settled=_auction.settled,
        ipfs_hash=_auction.ipfs_hash,
        params=_auction.params,
    )

    log AuctionBid(_auction.auction_id, bidder, msg.sender, total_bid, _extended)
    if _extended:
        log AuctionExtended(_auction.auction_id, _auction.end_time)


@internal
@view
def _minimum_total_bid(auction_id: uint256) -> uint256:
    _auction: Auction = self.auction_list[auction_id]
    assert _auction.start_time != 0, "!auctionId"
    assert not _auction.settled, "settled"
    if _auction.amount == 0:
        return _auction.params.reserve_price

    _min_pct: uint256 = _auction.params.min_bid_increment_percentage
    return _auction.amount + ((_auction.amount * _min_pct) // PRECISION)


@internal
@view
def _minimum_additional_bid(
    auction_id: uint256, bidder: address = empty(address)
) -> uint256:
    _total_min: uint256 = self._minimum_total_bid(auction_id)
    if bidder == empty(address):
        return _total_min

    pending: uint256 = self.auction_pending_returns[auction_id][bidder]
    if pending >= _total_min:
        return 0
    return _total_min - pending


@internal
@view
def _check_caller(
    _account: address, _caller: address, _req_status: ApprovalStatus
):
    if _account != _caller:
        _status: ApprovalStatus = self.approved_caller[_account][_caller]
        if _status == ApprovalStatus.BidAndWithdraw:
            return
        assert (_status == _req_status), "!caller"


@external
@view
def get_dy(_token_addr: IERC20, _dx: uint256) -> uint256:
    return staticcall self.additional_tokens[_token_addr].get_dy(_dx)


@external
@view
def get_dx(_token_addr: IERC20, _dy: uint256) -> uint256:
    return staticcall self.additional_tokens[_token_addr].get_dx(_dy)


@external
@view
def safe_get_dx(_token_addr: IERC20, _dy: uint256) -> uint256:
    """
    @dev A gas fuzzling function, recommend not to use in smart contracts
    @return A safe dx above the minimum required to guarantee dy
    """

    _actual_dy: uint256 = 0
    _dx: uint256 = staticcall self.additional_tokens[_token_addr].get_dx(_dy)
    for _i: uint256 in range(10):
        _actual_dy = staticcall self.additional_tokens[_token_addr].get_dy(_dx)
        if _actual_dy >= _dy:
            break
        else:
            _dx = _dx * 10000000001 // 10000000000
    assert _actual_dy >= _dy
    return _dx


@external
@view
def minimum_total_bid(auction_id: uint256) -> uint256:
    """
    @notice Returns the minimum bid one must place for a given auction
    @return Minimum bid in the payment token
    """
    return self._minimum_total_bid(auction_id)


@external
@view
def minimum_additional_bid_for_user(
    auction_id: uint256, user: address
) -> uint256:
    """
    @notice Returns the minimum additional amount a user must add to become top bidder for an auction
    @return Required amount to bid in the payment token
    """
    return self._minimum_additional_bid(auction_id, user)


@external
@view
def pending_returns(user: address) -> uint256:
    """
    @notice Get total pending returns for a user across all auctions
    @param user The address to check pending returns for
    @return Total pending returns amount
    """
    total_pending: uint256 = 0
    for i: uint256 in range(MAX_AUCTIONS):
        auction_id: uint256 = i + 1
        if auction_id > self.auction_id:
            break
        total_pending += self.auction_pending_returns[auction_id][user]
    return total_pending


# ============================================================================================
# External functions
# ============================================================================================

@external
@nonreentrant
def create_new_auction(ipfs_hash: String[46] = "") -> uint256:
    """
    @dev Create a new auction
    @param ipfs_hash The IPFS hash of the auction metadata
    @return New auction id
    """
    pausable._check_unpaused()
    ownable._check_owner()
    return self._create_auction(ipfs_hash, self._default_auction_params())


@external
@nonreentrant
def create_custom_auction(
    time_buffer: uint256,
    reserve_price: uint256,
    min_bid_increment_percentage: uint256,
    duration: uint256,
    ipfs_hash: String[46] = ""
) -> uint256:
    """
    @dev Create a new auction with custom parameters instead of defaults
    @param ipfs_hash The IPFS hash of the auction metadata
    @return New auction id
    """
    assert duration >= MIN_DURATION and duration <= MAX_DURATION, "!duration"

    pausable._check_unpaused()
    ownable._check_owner()
    return self._create_auction(
        ipfs_hash,
        AuctionParams(
            time_buffer=time_buffer,
            reserve_price=reserve_price,
            min_bid_increment_percentage=min_bid_increment_percentage,
            duration=duration,
        ),
    )


@external
@nonreentrant
def settle_auction(auction_id: uint256):
    """
    @dev Settle an auction
    """
    pausable._check_unpaused()
    self._settle_auction(auction_id)


@external
@nonreentrant
def settle_and_create_auction(auction_id: uint256, ipfs_hash: String[46] = ""):
    """
    @dev Settle the current auction and create a new one.
      Throws if the auction house is not paused.
    """
    pausable._check_paused()
    self._settle_auction(auction_id)
    self._create_auction(ipfs_hash, self._default_auction_params())


@external
@nonreentrant
def create_bid(
    auction_id: uint256,
    bid_amount: uint256,
    on_behalf_of: address = msg.sender,
):
    """
    @dev Create a bid using the primary payment token
    """
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    self._collect_payment(auction_id, bid_amount, on_behalf_of)
    self._create_bid(auction_id, bid_amount, on_behalf_of)


@external
@nonreentrant
def create_bid_with_token(
    auction_id: uint256,
    token_amount: uint256,
    token: IERC20,
    min_dy: uint256,
    on_behalf_of: address = msg.sender,
):
    """
    @notice Create a bid using an alternative token
    @dev Must have approved the token for use with this contract
    @param auction_id An active auction
    @param token_amount Amount of the alternative token
    @param token Address of the token
    @param min_dy To protect against slippage, min amount of payment token to receive
    @param on_behalf_of User to bid on behalf of
    """
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)

    trader: TokenTrader = self.additional_tokens[token]
    assert trader.address != empty(address), "!trader"

    # Transfer token to contract, or revert
    extcall token.transferFrom(on_behalf_of, self, token_amount)

    # Exchange, or revert
    value_traded: uint256 = extcall trader.exchange(token_amount, min_dy, self)

    # Bid
    self._create_bid(auction_id, value_traded, on_behalf_of)


@external
@nonreentrant
def withdraw(auction_id: uint256, on_behalf_of: address = msg.sender):
    """
    @dev Withdraw tokens after losing auction
    """
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.WithdrawOnly)
    pending: uint256 = self.auction_pending_returns[auction_id][on_behalf_of]
    assert pending > 0, "!pending"
    self.auction_pending_returns[auction_id][on_behalf_of] = 0
    assert extcall self.payment_token.transfer(
        on_behalf_of, pending, default_return_value=True
    ), "!transfer"
    log Withdraw(auction_id, on_behalf_of, msg.sender, pending)


@external
@nonreentrant
def withdraw_multiple(
    auction_ids: DynArray[uint256, MAX_WITHDRAWALS],
    on_behalf_of: address = msg.sender,
):
    """
    @dev Withdraw from multiple auctions at once
    """
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.WithdrawOnly)
    total_pending: uint256 = 0
    for auction_id: uint256 in auction_ids:
        pending: uint256 = self.auction_pending_returns[auction_id][
            on_behalf_of
        ]
        if pending > 0:
            total_pending += pending
            self.auction_pending_returns[auction_id][on_behalf_of] = 0
            log Withdraw(auction_id, on_behalf_of, msg.sender, pending)
    assert total_pending > 0, "!pending"
    assert extcall self.payment_token.transfer(
        on_behalf_of, total_pending, default_return_value=True
    ), "!transfer"


@external
@nonreentrant
def withdraw_stale(addresses: DynArray[address, MAX_WITHDRAWALS]):
    """
    @dev Admin function to withdraw pending returns that have not been claimed
    """
    ownable._check_owner()

    total_fee: uint256 = 0
    for _address: address in addresses:
        # Sum up pending returns across all auctions
        pending_amount: uint256 = 0
        for i: uint256 in range(MAX_AUCTIONS):
            auction_id: uint256 = i + 1
            if auction_id > self.auction_id:
                break

            auction_pending: uint256 = self.auction_pending_returns[auction_id][
                _address
            ]
            if auction_pending > 0:
                pending_amount += auction_pending
                self.auction_pending_returns[auction_id][_address] = 0
        if pending_amount == 0:
            continue

        fee: uint256 = pending_amount * 5 // 100
        withdrawer_return: uint256 = pending_amount - fee
        assert extcall self.payment_token.transfer(
            _address, withdrawer_return
        ), "Token transfer failed"
        total_fee += fee

    if total_fee > 0:
        assert extcall self.payment_token.transfer(
            self.fee_receiver, total_fee
        ), "Fee transfer failed"


@external
def set_approved_caller(caller: address, status: ApprovalStatus):
    """
    @dev Set approval status for a caller
    """
    self.approved_caller[msg.sender][caller] = status
    log ApprovedCallerSet(msg.sender, caller, status)


# ============================================================================================
# Owner functions
# ============================================================================================

@external
def add_token_support(token: IERC20, trader: TokenTrader):
    """
    @notice Add support for an alternative payment token
    @dev Must be connected with a contract that supports token trading
    @param token The address of the ERC20 compatible token
    @param trader Address of a compatible trading contract
    """

    ownable._check_owner()
    assert token.address != empty(address), "!token"
    assert trader.address != empty(address), "!trader"
    assert token != self.payment_token, "!payment_token"

    self.additional_tokens[token] = trader
    self.supported_tokens.append(token)
    extcall token.approve(trader.address, max_value(uint256))
    log TokenSupportAdded(token.address, trader.address)


@external
def revoke_token_support(token_addr: IERC20):
    """
    @notice Remove support for an alternative payment token
    """
    ownable._check_owner()
    assert token_addr.address != empty(address), "!token"
    assert self.additional_tokens[token_addr].address != empty(
        address
    ), "!supported"
    self.additional_tokens[token_addr] = empty(TokenTrader)

    # Remove the token from supported_tokens
    for i: uint256 in range(MAX_TOKENS):
        if i >= len(self.supported_tokens):
            break

        if self.supported_tokens[i] == token_addr:
            # Swap with the last element and pop
            self.supported_tokens[i] = self.supported_tokens[
                len(self.supported_tokens) - 1
            ]
            self.supported_tokens.pop()
            break
    log TokenSupportRemoved(token_addr.address)


@external
def set_default_time_buffer(_time_buffer: uint256):
    ownable._check_owner()
    self.default_time_buffer = _time_buffer
    log DefaultAuctionTimeBufferUpdated(_time_buffer)


@external
def set_default_reserve_price(_reserve_price: uint256):
    ownable._check_owner()
    self.default_reserve_price = _reserve_price
    log DefaultAuctionReservePriceUpdated(_reserve_price)


@external
def set_default_min_bid_increment_percentage(_percentage: uint256):
    ownable._check_owner()
    assert (
        _percentage >= MIN_BID_INCREMENT_PERCENTAGE_
        and _percentage <= MAX_BID_INCREMENT_PERCENTAGE
    ), "!percentage"
    self.default_min_bid_increment_percentage = _percentage
    log DefaultAuctionMinBidIncrementPercentageUpdated(_percentage)


@external
def set_default_duration(_duration: uint256):
    ownable._check_owner()
    assert _duration >= MIN_DURATION and _duration <= MAX_DURATION, "!duration"
    self.default_duration = _duration
    log DefaultAuctionDurationUpdated(_duration)


@external
def set_fee_receiver(_fee_receiver: address):
    ownable._check_owner()
    assert _fee_receiver != empty(address), "!fee_receiver"
    self.fee_receiver = _fee_receiver
    log FeeReceiverUpdated(_fee_receiver)


@external
def set_fee(_fee: uint256):
    ownable._check_owner()
    assert _fee <= MAX_FEE, "!fee"
    self.fee = _fee
    log FeeUpdated(_fee)


# ============================================================================================
# Internal functions
# ============================================================================================

@internal
def _default_auction_params() -> AuctionParams:
    return AuctionParams(
        time_buffer=self.default_time_buffer,
        reserve_price=self.default_reserve_price,
        min_bid_increment_percentage=self.default_min_bid_increment_percentage,
        duration=self.default_duration,
    )


@internal
def _create_auction(
    ipfs_hash: String[46], params: AuctionParams
) -> uint256:

    _start_time: uint256 = block.timestamp
    _end_time: uint256 = _start_time + params.duration
    _auction_id: uint256 = self.auction_id + 1

    self.auction_id = _auction_id
    self.auction_list[_auction_id] = Auction(
        auction_id=_auction_id,
        amount=0,
        start_time=_start_time,
        end_time=_end_time,
        bidder=empty(address),
        settled=False,
        ipfs_hash=ipfs_hash,
        params=params,
    )

    log AuctionCreated(_auction_id, _start_time, _end_time, ipfs_hash)
    return _auction_id
