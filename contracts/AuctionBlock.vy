# @version 0.4.0

"""
@title Auction Block
@license MIT
@author Leviathan
@notice Auction block for standard single-price auctions
"""

from ethereum.ercs import IERC20

from .imports import ownable_2step as ownable
from .imports import pausable


# ============================================================================================
# 🧩 Interfaces
# ============================================================================================

interface AuctionDirectory:
    def mint_nft(owner: address, auction_id: uint256): nonpayable


# ============================================================================================
# ⚙️ Modules
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
# 🏢 Structs
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
# 📣 Events
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


event AuctionCreated:
    auction_id: indexed(uint256)
    start_time: uint256
    end_time: uint256
    ipfs_hash: String[46]


event AuctionSettled:
    auction_id: indexed(uint256)
    winner: address
    amount: uint256


event AuctionNullified:
    auction_id: indexed(uint256)


event Withdraw:
    auction_id: indexed(uint256)
    on_behalf_of: indexed(address)
    caller: indexed(address)
    amount: uint256


event ApprovedCallerSet:
    account: address
    caller: address
    status: ApprovalStatus


event FeeReceiverUpdated:
    fee_receiver: address


event FeePercentUpdated:
    fee_percent: uint256


event DirectorySet:
    directory_address: address


# ============================================================================================
# 📜 Constants
# ============================================================================================

MAX_WITHDRAWALS: constant(uint256) = 100
MAX_AUCTIONS: constant(uint256) = 10000
MAX_FEE_PERCENT: constant(uint256) = 100 * 10**8  # 100%
PERCENT_PRECISION: constant(uint256) = 100 * 10**8


# ============================================================================================
# 💾 Storage
# ============================================================================================

# Auction
default_time_buffer: public(uint256)
default_reserve_price: public(uint256)
default_min_bid_increment_percentage: public(uint256)
default_duration: public(uint256)

# Auction metadata: auction_id -> user -> ipfs
# Can append ad text or other data via IPFS
auction_metadata: public(HashMap[uint256, HashMap[address, String[46]]])

# Aution pending returns due to users: auction_id -> user -> returns
auction_pending_returns: public(HashMap[uint256, HashMap[address, uint256]])
auction_list: public(HashMap[uint256, Auction])
auction_id: public(uint256)

# User settings: user -> caller -> status
approved_caller: public(HashMap[address, HashMap[address, ApprovalStatus]])

# Tokens
payment_token: public(IERC20)
authorized_directory: public(AuctionDirectory)

# Fee configuration
fee_receiver: public(address)
fee_percent: public(uint256)


# ============================================================================================
# 🚧 Constructor
# ============================================================================================

@deploy
def __init__(
    payment_token: address,
    fee_receiver: address,
):
    assert payment_token != empty(address), "!payment_token"
    assert fee_receiver != empty(address), "!fee_receiver"

    ownable.__init__()
    pausable.__init__()

    # Defaults
    self.default_duration = 3600  # 1 hour
    self.default_time_buffer = 300  # 5 minutes
    self.default_reserve_price = 2 * 10**17  # 0.2 tokens
    self.default_min_bid_increment_percentage = 2 * 10**8  # 2%

    # Money
    self.payment_token = IERC20(payment_token)
    self.fee_receiver = fee_receiver
    self.fee_percent = 5 * 10**8  # 5%


# ============================================================================================
# 👀 View functions
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

        if self._is_auction_live(i + 1):
            active_auctions.append(i + 1)
    return active_auctions


@external
@view
def is_auction_live(auction_id: uint256) -> bool:
    return self._is_auction_live(auction_id)


@external
@view
def auction_remaining_time(auction_id: uint256) -> uint256:
    end_time: uint256 = self.auction_list[auction_id].end_time
    remaining_time: uint256 = 0
    if end_time > block.timestamp:
        remaining_time = end_time - block.timestamp
    return remaining_time


@external
@view
def auction_bid_by_user(auction_id: uint256, user: address) -> uint256:
    """
    @notice Get the total amount a user has bid on a specific auction
    @dev Returns the sum of current winning bid (if they're the winner) plus any pending returns
    @param auction_id The auction to check
    @param user The address to check bids for
    @return Total amount bid by user on this auction
    """
    auction: Auction = self.auction_list[auction_id]
    assert auction.start_time != 0, "!auction"

    total_bid: uint256 = 0

    # Add pending returns from previous outbid amounts
    total_bid += self.auction_pending_returns[auction_id][user]

    # Add current winning bid amount if they are the current winner
    if auction.bidder == user:
        total_bid += auction.amount

    return total_bid


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


# XXX
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
# ✍️ Write functions
# ============================================================================================


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
def create_bid(
    auction_id: uint256,
    bid_amount: uint256,
    ipfs_hash: String[46] = "",
    on_behalf_of: address = msg.sender,
):
    """
    @notice Create a bid using the contract's payment token
    @dev Create a bid using the primary payment token
    @param auction_id An active auction
    @param bid_amount The user's total bid, inclusive of prior bids
    @param on_behalf_of User to bid on behalf of
    @param ipfs_hash Optional data to register with the bid
    """
    self._create_bid(auction_id, bid_amount, ipfs_hash, on_behalf_of)


@external
@nonreentrant
def update_bid_metadata(
    auction_id: uint256,
    ipfs_hash: String[46],
    on_behalf_of: address = msg.sender,
):
    """
    @dev Update metadata
    """
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    self.auction_metadata[auction_id][on_behalf_of] = ipfs_hash


@external
@nonreentrant
def withdraw(
    auction_id: uint256, on_behalf_of: address = msg.sender
) -> uint256:
    """
    @dev Withdraw tokens after losing and settling auction
    """
    pausable._check_unpaused()
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.WithdrawOnly)
    assert self._is_auction_live(auction_id) == False, "!inactive"
    assert self._is_auction_settled(auction_id), "!settled"

    pending: uint256 = self.auction_pending_returns[auction_id][on_behalf_of]
    assert pending > 0, "!pending"

    self.auction_pending_returns[auction_id][on_behalf_of] = 0
    assert extcall self.payment_token.transfer(
        on_behalf_of, pending, default_return_value=True
    ), "!transfer"
    log Withdraw(auction_id, on_behalf_of, msg.sender, pending)
    return pending


@external
@nonreentrant
def withdraw_multiple(
    auction_ids: DynArray[uint256, MAX_WITHDRAWALS],
    on_behalf_of: address = msg.sender,
):
    """
    @dev Withdraw from multiple settled auctions at once
    """
    pausable._check_unpaused()
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.WithdrawOnly)
    total_pending: uint256 = 0
    settled_auction_exists: bool = False
    for auction_id: uint256 in auction_ids:
        if self._is_auction_live(auction_id):
            continue

        if not self._is_auction_settled(auction_id):
            continue

        settled_auction_exists = True
        pending: uint256 = self.auction_pending_returns[auction_id][
            on_behalf_of
        ]
        if pending > 0:
            total_pending += pending
            self.auction_pending_returns[auction_id][on_behalf_of] = 0
            log Withdraw(auction_id, on_behalf_of, msg.sender, pending)
    assert settled_auction_exists, "!settled"
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
    pausable._check_unpaused()

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

        fee: uint256 = pending_amount * self.fee_percent // PERCENT_PRECISION
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
# 👑 Owner functions
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
    ipfs_hash: String[46] = "",
) -> uint256:
    """
    @dev Create a new auction with custom parameters instead of defaults
    @param ipfs_hash The IPFS hash of the auction metadata
    @return New auction id
    """
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
def nullify_auction(auction_id: uint256):
    """
    @dev In the event of an emergency, pause all functions except allowing auction nullification
    """
    ownable._check_owner()
    assert self._is_auction_settled(auction_id) == False, "settled"

    _auction: Auction = self.auction_list[auction_id]
    _winner: address = _auction.bidder
    _win_bid: uint256 = _auction.amount

    self.auction_list[auction_id] = Auction(
        auction_id=_auction.auction_id,
        amount=0,
        start_time=_auction.start_time,
        end_time=block.timestamp - 1,
        bidder=empty(address),
        settled=True,
        ipfs_hash=_auction.ipfs_hash,
        params=_auction.params,
    )

    self.auction_pending_returns[auction_id][_winner] = _win_bid

    log AuctionNullified(auction_id)


@external
def set_fee_receiver(_fee_receiver: address):
    ownable._check_owner()
    assert _fee_receiver != empty(address), "!fee_receiver"
    self.fee_receiver = _fee_receiver
    log FeeReceiverUpdated(_fee_receiver)


@external
def set_fee_percent(_fee: uint256):
    ownable._check_owner()
    assert _fee <= MAX_FEE_PERCENT, "!fee"
    self.fee_percent = _fee
    log FeePercentUpdated(_fee)


@external
def set_approved_directory(directory_address: address):
    """
    @dev Authorized directory contract with permissions
    """
    ownable._check_owner()
    self.authorized_directory = AuctionDirectory(directory_address)
    log DirectorySet(directory_address)


@external
def recover_erc20(token_addr: address, amount: uint256):
    """
    @notice Recover ERC20 tokens accidentally sent to contract
    @dev Only callable by owner. If recovering payment token, ensures auction funds are protected
    @param token_addr The token contract address
    @param amount Amount of tokens to recover
    """
    ownable._check_owner()
    token: IERC20 = IERC20(token_addr)

    # Special handling for payment token to protect auction funds
    if token.address == self.payment_token.address:
        required_balance: uint256 = 0

        # Calculate total required balance for all auctions
        for i: uint256 in range(MAX_AUCTIONS):
            auction_id: uint256 = i + 1
            if auction_id > self.auction_id:
                break

            auction: Auction = self.auction_list[auction_id]
            # Include active bid amount if auction not settled
            if not auction.settled:
                required_balance += auction.amount
        current_balance: uint256 = staticcall token.balanceOf(self)
        assert (
            current_balance - amount >= required_balance
        ), "cannot recover auction funds"

    assert extcall token.transfer(ownable.owner, amount), "transfer failed"


# ============================================================================================
# 🏠 Internal functions
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
def _create_auction(ipfs_hash: String[46], params: AuctionParams) -> uint256:
    pausable._check_unpaused()
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


@internal
def _settle_auction(auction_id: uint256):
    _auction: Auction = self.auction_list[auction_id]
    assert _auction.start_time != 0, "!auction"
    assert self._is_auction_settled(auction_id) == False, "settled"
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
        fee_amount: uint256 = (
            _auction.amount * self.fee_percent // PERCENT_PRECISION
        )
        remaining_amount: uint256 = _auction.amount - fee_amount

        if fee_amount > 0:
            assert extcall self.payment_token.transfer(
                self.fee_receiver, fee_amount, default_return_value=True
            ), "!fee transfer"

        assert extcall self.payment_token.transfer(
            ownable.owner, remaining_amount, default_return_value=True
        ), "!owner transfer"

    if self.authorized_directory.address != empty(address):
        extcall self.authorized_directory.mint_nft(_auction.bidder, auction_id)

    log AuctionSettled(_auction.auction_id, _auction.bidder, _auction.amount)


@internal
def _collect_payment(
    auction_id: uint256,
    total_bid: uint256,
    bidder: address,
    token: IERC20 = empty(IERC20),  # Optional token param
    token_amount: uint256 = 0,  # Amount of alternate token provided
) -> uint256:
    """
    @dev Collect payment either in payment or alternate token
    @return Final amount of payment token collected (including any pending returns used)
    """
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
        # Directory handles privileges, auction contracts invisible to user
        token_source: address = bidder
        if msg.sender == self.authorized_directory.address:
            token_source = self.authorized_directory.address

        assert extcall self.payment_token.transferFrom(
            token_source, self, tokens_needed, default_return_value=True
        ), "!transfer"

    return total_bid


@internal
def _create_bid(
    auction_id: uint256,
    bid_amount: uint256,
    ipfs_hash: String[46],
    on_behalf_of: address,
    token: IERC20 = empty(IERC20),
    min_dy: uint256 = 0,
):
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)

    payment_amount: uint256 = self._collect_payment(
        auction_id, bid_amount, on_behalf_of, token, min_dy
    )
    self._register_bid(auction_id, payment_amount, on_behalf_of)

    # User may be requested to register data with their bid
    if ipfs_hash != "":
        self.auction_metadata[auction_id][on_behalf_of] = ipfs_hash


@internal
def _register_bid(auction_id: uint256, total_bid: uint256, bidder: address):
    pausable._check_unpaused()

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

    _end_time: uint256 = _auction.end_time

    _extended: bool = _auction.end_time - block.timestamp < _time_buffer
    if _extended:
        _end_time = block.timestamp + _time_buffer

    self.auction_list[auction_id] = Auction(
        auction_id=_auction.auction_id,
        amount=total_bid,
        start_time=_auction.start_time,
        end_time=_end_time,
        bidder=bidder,
        settled=_auction.settled,
        ipfs_hash=_auction.ipfs_hash,
        params=_auction.params,
    )

    log AuctionBid(
        _auction.auction_id, bidder, msg.sender, total_bid, _extended
    )
    if _extended:
        log AuctionExtended(_auction.auction_id, _auction.end_time)


@internal
@view
def _minimum_total_bid(auction_id: uint256) -> uint256:
    _auction: Auction = self.auction_list[auction_id]
    assert _auction.start_time != 0, "!auctionId"
    assert not self._is_auction_settled(auction_id), "settled"

    if _auction.amount == 0:
        return _auction.params.reserve_price

    _min_pct: uint256 = _auction.params.min_bid_increment_percentage
    return _auction.amount + ((_auction.amount * _min_pct) // PERCENT_PRECISION)


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
    # Directory contract assumes onus of confirming status
    if _account != _caller and msg.sender != self.authorized_directory.address:
        _status: ApprovalStatus = self.approved_caller[_account][_caller]
        if _status == ApprovalStatus.BidAndWithdraw:
            return
        assert (_status == _req_status), "!caller"


@internal
@view
def _is_auction_settled(auction_id: uint256) -> bool:
    return self.auction_list[auction_id].settled


@internal
@view
def _is_auction_live(auction_id: uint256) -> bool:
    """
    @dev Note an auction will be considered live even if the contract is paused.
    """
    _is_live: bool = False
    _auction: Auction = self.auction_list[auction_id]
    if (
        _auction.start_time <= block.timestamp
        and block.timestamp <= _auction.end_time
        and not _auction.settled
    ):
        _is_live = True

    return _is_live
