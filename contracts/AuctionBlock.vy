# @version 0.4.0

# @notice Squid Auction Block with ERC20 payments
# @author Leviathan
# @license MIT

from ethereum.ercs import IERC20

# Structures

struct Auction:
    auction_id: uint256
    amount: uint256
    start_time: uint256
    end_time: uint256
    bidder: address
    settled: bool
    ipfs_hash: String[46]


# Interfaces
interface TokenTrader:
    def exchange(
        _dx: uint256, _min_dy: uint256, _from: address = msg.sender
    ) -> uint256: nonpayable
    def get_dy(_dx: uint256) -> uint256: view


# Events

event AuctionBid:
    _auction_id: indexed(uint256)
    _sender: address
    _value: uint256
    _extended: bool


event AuctionExtended:
    _auction_id: indexed(uint256)
    _end_time: uint256


event AuctionTimeBufferUpdated:
    _time_buffer: uint256


event AuctionReservePriceUpdated:
    _reserve_price: uint256


event AuctionMinBidIncrementPercentageUpdated:
    _min_bid_increment_percentage: uint256


event AuctionDurationUpdated:
    _duration: uint256


event AuctionCreated:
    _auction_id: indexed(uint256)
    _start_time: uint256
    _end_time: uint256
    _ipfs_hash: String[46]


event AuctionSettled:
    _auction_id: indexed(uint256)
    _winner: address
    _amount: uint256


event Withdraw:
    _withdrawer: indexed(address)
    _amount: uint256


event DelegatedBidderUpdated:
    _bidder: indexed(address)
    _allowed: bool


IDENTITY_PRECOMPILE: constant(
    address
) = 0x0000000000000000000000000000000000000004

ADMIN_MAX_WITHDRAWALS: constant(uint256) = 100
MAX_AUCTION_ITERATIONS: constant(uint256) = 100


# Auction
time_buffer: public(uint256)
reserve_price: public(uint256)
min_bid_increment_percentage: public(uint256)
duration: public(uint256)
auction_id: public(uint256)

auction_pending_returns: public(HashMap[uint256, HashMap[address, uint256]])
delegated_bidders: public(HashMap[address, bool])
auction_list: public(HashMap[uint256, Auction])

# Payment token
payment_token: public(IERC20)
additional_tokens: public(HashMap[IERC20, TokenTrader])

# Permissions
owner: public(address)

# Pause
paused: public(bool)

# Proceeds
proceeds_receiver: public(address)
proceeds_receiver_split_percentage: public(uint256)


@deploy
def __init__(
    _time_buffer: uint256,
    _reserve_price: uint256,
    _min_bid_increment_percentage: uint256,
    _duration: uint256,
    _proceeds_receiver: address,
    _proceeds_receiver_split_percentage: uint256,
    _payment_token: IERC20,
):
    self.time_buffer = _time_buffer
    self.reserve_price = _reserve_price
    self.min_bid_increment_percentage = _min_bid_increment_percentage
    self.duration = _duration
    self.owner = msg.sender
    self.paused = True
    self.proceeds_receiver = _proceeds_receiver
    self.proceeds_receiver_split_percentage = (
        _proceeds_receiver_split_percentage
    )
    self.payment_token = _payment_token


# VIEWS

@external
@view
def current_auctions() -> DynArray[uint256, 100]:
    """
    @dev Returns an array of currently active auction IDs based on timestamp
    @return Array of auction IDs that are currently active (between start and end time)
    """
    active_auctions: DynArray[uint256, 100] = []

    for i: uint256 in range(100):
        if i + 1 > self.auction_id:
            break

        auction: Auction = self.auction_list[i + 1]
        # Check if auction is currently active based on timestamp
        if (
            auction.start_time <= block.timestamp
            and block.timestamp <= auction.end_time
            and not auction.settled
        ):
            active_auctions.append(i + 1)
    return active_auctions


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
    for i: uint256 in range(MAX_AUCTION_ITERATIONS):
        auction_id: uint256 = i + 1
        if auction_id > self.auction_id:
            break
        total_pending += self.auction_pending_returns[auction_id][user]
    return total_pending


# CALLS

@external
@nonreentrant
def settle_auction(auction_id: uint256):
    """
    @dev Settle an auction.
      Throws if the auction house is paused.
    """
    assert self.paused == False, "Auction house is paused"
    self._settle_auction(auction_id)


@external
@nonreentrant
def create_new_auction(ipfs_hash: String[46] = "") -> uint256:
    """
    @dev Create a new auction.
    @return New auction id
      Throws if the auction house is paused.
    """
    assert self.paused == False, "Auction house is paused"
    self._create_auction(ipfs_hash)
    return self.auction_id


@external
@nonreentrant
def settle_and_create_auction(auction_id: uint256, ipfs_hash: String[46] = ""):
    """
    @dev Settle the current auction and create a new one.
      Throws if the auction house is not paused.
    """
    assert self.paused == True, "Auction house is not paused"
    self._settle_auction(auction_id)
    self._create_auction(ipfs_hash)


@external
def set_delegated_bidder(_bidder: address, _allowed: bool):
    """
    @dev Allow or revoke an address to bid on behalf of others
    @param _bidder The address to update delegation status for
    @param _allowed Whether the address should be allowed to bid on behalf of others
    """
    assert msg.sender == self.owner, "Caller is not the owner"
    self.delegated_bidders[_bidder] = _allowed
    log DelegatedBidderUpdated(_bidder, _allowed)


@external
@nonreentrant
def create_bid(
    auction_id: uint256,
    bid_amount: uint256,
    on_behalf_of: address = empty(address),
):
    """
    @dev Create a bid using ERC20 tokens, optionally on behalf of another address
    @param auction_id The ID of the auction to bid on
    @param bid_amount The amount to bid
    @param on_behalf_of Optional address to bid on behalf of. If empty, bid is from msg.sender
    """
    # If bidding on behalf of someone else, verify permissions
    bidder: address = msg.sender
    if on_behalf_of != empty(address):
        assert self.delegated_bidders[
            msg.sender
        ], "Not authorized to bid on behalf"
        bidder = on_behalf_of

    self._create_bid(auction_id, bid_amount, bidder)


@external
@nonreentrant
def create_bid_with_misc_token(
    auction_id: uint256,
    bid_amount: uint256,
    token: IERC20,
    min_dy: uint256,
    on_behalf_of: address = empty(address),
):
    """
    @dev Create a bid using ERC20 tokens, optionally on behalf of another address
    @param auction_id The ID of the auction to bid on
    @param bid_amount The amount to bid
    @param on_behalf_of Optional address to bid on behalf of. If empty, bid is from msg.sender
    """
    # If bidding on behalf of someone else, verify permissions
    bidder: address = msg.sender
    if on_behalf_of != empty(address):
        assert self.delegated_bidders[
            msg.sender
        ], "Not authorized to bid on behalf"
        bidder = on_behalf_of

    trader: TokenTrader = self.additional_tokens[token]
    assert trader.address != empty(address), "Not registered"
    value_traded: uint256 = extcall trader.exchange(
        bid_amount, min_dy, bidder
    )  # Pass the bidder address
    self._create_bid(auction_id, value_traded, bidder)


@external
@nonreentrant
def withdraw():
    """
    @dev Withdraw ERC20 tokens after losing auction
    """
    pending_amount: uint256 = 0
    # Sum up pending returns across all auctions
    for i: uint256 in range(MAX_AUCTION_ITERATIONS):
        auction_id: uint256 = i + 1
        if auction_id > self.auction_id:
            break

        auction_pending: uint256 = self.auction_pending_returns[auction_id][
            msg.sender
        ]
        if auction_pending > 0:
            pending_amount += auction_pending
            self.auction_pending_returns[auction_id][msg.sender] = 0
    assert pending_amount > 0, "No pending returns"
    assert extcall self.payment_token.transfer(
        msg.sender, pending_amount
    ), "Token transfer failed"
    log Withdraw(msg.sender, pending_amount)


@external
@nonreentrant
def withdraw_stale(addresses: DynArray[address, ADMIN_MAX_WITHDRAWALS]):
    """
    @dev Admin function to withdraw pending returns that have not been claimed
    """
    assert msg.sender == self.owner, "Caller is not the owner"

    total_fee: uint256 = 0
    for _address: address in addresses:
        # Sum up pending returns across all auctions
        pending_amount: uint256 = 0
        for i: uint256 in range(MAX_AUCTION_ITERATIONS):
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


        # Take a 5% fee
        fee: uint256 = pending_amount * 5 // 100
        withdrawer_return: uint256 = pending_amount - fee
        assert extcall self.payment_token.transfer(
            _address, withdrawer_return
        ), "Token transfer failed"
        total_fee += fee

    if total_fee > 0:
        assert extcall self.payment_token.transfer(
            self.owner, total_fee
        ), "Fee transfer failed"


@external
def pause():
    assert msg.sender == self.owner, "Caller is not the owner"
    self._pause()


@external
def unpause():
    assert msg.sender == self.owner, "Caller is not the owner"
    self._unpause()


@external
def set_time_buffer(_time_buffer: uint256):
    assert msg.sender == self.owner, "Caller is not the owner"
    self.time_buffer = _time_buffer
    log AuctionTimeBufferUpdated(_time_buffer)


@external
def set_reserve_price(_reserve_price: uint256):
    assert msg.sender == self.owner, "Caller is not the owner"
    self.reserve_price = _reserve_price
    log AuctionReservePriceUpdated(_reserve_price)


@external
def set_min_bid_increment_percentage(_min_bid_increment_percentage: uint256):
    assert msg.sender == self.owner, "Caller is not the owner"
    assert (
        _min_bid_increment_percentage >= 2
        and _min_bid_increment_percentage <= 15
    ), "_min_bid_increment_percentage out of range"
    self.min_bid_increment_percentage = _min_bid_increment_percentage
    log AuctionMinBidIncrementPercentageUpdated(_min_bid_increment_percentage)


@external
def set_duration(_duration: uint256):
    assert msg.sender == self.owner, "Caller is not the owner"
    assert _duration >= 3600 and _duration <= 259200, "_duration out of range"
    self.duration = _duration
    log AuctionDurationUpdated(_duration)


@external
def set_owner(_owner: address):
    assert msg.sender == self.owner, "Caller is not the owner"
    assert _owner != empty(address), "Cannot set owner to zero address"
    self.owner = _owner


# INTERNAL

@internal
def _create_auction(ipfs_hash: String[46]):
    _start_time: uint256 = block.timestamp
    _end_time: uint256 = _start_time + self.duration
    self.auction_id += 1

    self.auction_list[self.auction_id] = Auction(
        auction_id=self.auction_id,
        amount=0,
        start_time=_start_time,
        end_time=_end_time,
        bidder=empty(address),
        settled=False,
        ipfs_hash=ipfs_hash,
    )

    log AuctionCreated(self.auction_id, _start_time, _end_time, ipfs_hash)


@internal
def _settle_auction(auction_id: uint256):
    _auction: Auction = self.auction_list[auction_id]
    assert _auction.start_time != 0, "Auction hasn't begun"
    assert _auction.settled == False, "Auction has already been settled"
    assert block.timestamp > _auction.end_time, "Auction hasn't completed"

    self.auction_list[auction_id] = Auction(
        auction_id=_auction.auction_id,
        amount=_auction.amount,
        start_time=_auction.start_time,
        end_time=_auction.end_time,
        bidder=_auction.bidder,
        settled=True,
        ipfs_hash=_auction.ipfs_hash,
    )

    if _auction.amount > 0:
        fee: uint256 = (
            _auction.amount * self.proceeds_receiver_split_percentage
        ) // 100
        owner_amount: uint256 = _auction.amount - fee
        assert extcall self.payment_token.transfer(
            self.owner, owner_amount
        ), "Owner payment failed"
        assert extcall self.payment_token.transfer(
            self.proceeds_receiver, fee
        ), "Fee payment failed"

    log AuctionSettled(_auction.auction_id, _auction.bidder, _auction.amount)


@internal
def _create_bid(auction_id: uint256, total_bid: uint256, bidder: address):
    """
    @dev Internal function to create a bid
    @param auction_id The ID of the auction
    @param total_bid The bid amount to set (not the amount of additional tokens to send)
    @param bidder The address that will be recorded as the bidder
    """
    _auction: Auction = self.auction_list[auction_id]

    assert _auction.auction_id == auction_id, "Invalid auction ID"
    assert block.timestamp < _auction.end_time, "Auction expired"
    assert total_bid >= self.reserve_price, "Must send at least reservePrice"
    assert total_bid >= self._minimum_total_bid(
        auction_id
    ), "Must send more than last bid by min_bid_increment_percentage amount"

    # If this is a delegated bid, we need to transfer from the actual bidder
    pending_amount: uint256 = self.auction_pending_returns[auction_id][bidder]
    tokens_needed: uint256 = total_bid
    if pending_amount > 0:
        if pending_amount >= total_bid:
            # Use entire bid amount from pending returns
            self.auction_pending_returns[auction_id][bidder] = (
                pending_amount - total_bid
            )
            tokens_needed = 0
        else:
            # Use all pending returns and require additional tokens
            self.auction_pending_returns[auction_id][bidder] = 0
            tokens_needed = total_bid - pending_amount
    if tokens_needed > 0:
        assert extcall self.payment_token.transferFrom(
            bidder, self, tokens_needed
        ), "Token transfer failed"

    last_bidder: address = _auction.bidder
    if last_bidder != empty(address):
        # Store pending return for the auction it came from
        self.auction_pending_returns[auction_id][last_bidder] += _auction.amount

    extended: bool = _auction.end_time - block.timestamp < self.time_buffer
    self.auction_list[auction_id] = Auction(
        auction_id=_auction.auction_id,
        amount=total_bid,
        start_time=_auction.start_time,
        end_time=_auction.end_time
        if not extended
        else block.timestamp + self.time_buffer,
        bidder=bidder,
        settled=_auction.settled,
        ipfs_hash=_auction.ipfs_hash,
    )

    log AuctionBid(_auction.auction_id, bidder, total_bid, extended)

    if extended:
        log AuctionExtended(_auction.auction_id, _auction.end_time)


@internal
def _pause():
    self.paused = True


@internal
def _unpause():
    self.paused = False


@internal
@view
def _minimum_total_bid(auction_id: uint256) -> uint256:
    _auction: Auction = self.auction_list[auction_id]
    assert _auction.start_time != 0, "Invalid auction ID"
    assert not _auction.settled, "Auction is settled"
    if _auction.amount == 0:
        return self.reserve_price

    _min_pct: uint256 = self.min_bid_increment_percentage
    return _auction.amount + ((_auction.amount * _min_pct) // 100)


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


# Trade
@external
def add_token_support(token_addr: IERC20, trader_addr: TokenTrader):
    """
    @notice Adds support for trading a specific token
    @param token_addr The token address to revoke trading support for
    @param trader_addr Contract which handles trading
    """
    assert msg.sender == self.owner, "Caller is not the owner"
    assert token_addr.address != empty(address), "Invalid token address"
    self.additional_tokens[token_addr] = trader_addr
    extcall token_addr.approve(trader_addr.address, max_value(uint256))


@external
def revoke_token_support(token_addr: IERC20):
    """
    @notice Revokes support for trading a specific token
    @param token_addr The token address to revoke trading support for
    """
    assert msg.sender == self.owner, "Caller is not the owner"
    assert token_addr.address != empty(address), "Invalid token address"
    assert self.additional_tokens[token_addr].address != empty(
        address
    ), "Token not supported"
    self.additional_tokens[token_addr] = empty(TokenTrader)
