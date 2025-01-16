# @version 0.4.0

# @notice Squid Auction Block with ERC20 payments
# @author Leviathan
# @license MIT

from ethereum.ercs import IERC20

struct Auction:
    auction_id: uint256
    amount: uint256
    start_time: uint256
    end_time: uint256
    bidder: address
    settled: bool


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


event AuctionSettled:
    _auction_id: indexed(uint256)
    _winner: address
    _amount: uint256


event Withdraw:
    _withdrawer: indexed(address)
    _amount: uint256


IDENTITY_PRECOMPILE: constant(
    address
) = 0x0000000000000000000000000000000000000004

ADMIN_MAX_WITHDRAWALS: constant(uint256) = 100


# Auction
time_buffer: public(uint256)
reserve_price: public(uint256)
min_bid_increment_percentage: public(uint256)
duration: public(uint256)
pending_returns: public(HashMap[address, uint256])
auction_list: public(HashMap[uint256, Auction])
auction_id: public(uint256)

# Payment token
payment_token: public(IERC20)

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
    _payment_token: IERC20
):
    self.time_buffer = _time_buffer
    self.reserve_price = _reserve_price
    self.min_bid_increment_percentage = _min_bid_increment_percentage
    self.duration = _duration
    self.owner = msg.sender
    self.paused = True
    self.proceeds_receiver = _proceeds_receiver
    self.proceeds_receiver_split_percentage = _proceeds_receiver_split_percentage
    self.payment_token = _payment_token


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
        if (auction.start_time <= block.timestamp and 
            block.timestamp <= auction.end_time and 
            not auction.settled):
            active_auctions.append(i + 1)
    
    return active_auctions


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
def create_new_auction():
    """
    @dev Create a new auction.
      Throws if the auction house is paused.
    """
    assert self.paused == False, "Auction house is paused"
    self._create_auction()


@external
@nonreentrant
def settle_and_create_auction(auction_id: uint256):
    """
    @dev Settle the current auction and create a new one.
      Throws if the auction house is not paused.
    """
    assert self.paused == True, "Auction house is not paused"
    self._settle_auction(auction_id)
    self._create_auction()


@external
@nonreentrant
def create_bid(auction_id: uint256, bid_amount: uint256):
    """
    @dev Create a bid using ERC20 tokens
    """
    self._create_bid(auction_id, bid_amount)


@external
@nonreentrant
def withdraw():
    """
    @dev Withdraw ERC20 tokens after losing auction
    """
    pending_amount: uint256 = self.pending_returns[msg.sender]
    assert pending_amount > 0, "No pending returns"
    
    self.pending_returns[msg.sender] = 0
    assert extcall self.payment_token.transfer(msg.sender, pending_amount), "Token transfer failed"
    
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
        pending_amount: uint256 = self.pending_returns[_address]
        if pending_amount == 0:
            continue
            
        # Take a 5% fee
        fee: uint256 = pending_amount * 5 // 100
        withdrawer_return: uint256 = pending_amount - fee
        self.pending_returns[_address] = 0
        
        assert extcall self.payment_token.transfer(_address, withdrawer_return), "Token transfer failed"
        total_fee += fee

    if total_fee > 0:
        assert extcall self.payment_token.transfer(self.owner, total_fee), "Fee transfer failed"


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


@internal
def _create_auction():
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
    )

    log AuctionCreated(self.auction_id, _start_time, _end_time)


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
        settled=True
    )

    if _auction.amount > 0:
        fee: uint256 = (_auction.amount * self.proceeds_receiver_split_percentage) // 100
        owner_amount: uint256 = _auction.amount - fee
        
        assert extcall self.payment_token.transfer(self.owner, owner_amount), "Owner payment failed"
        assert extcall self.payment_token.transfer(self.proceeds_receiver, fee), "Fee payment failed"

    log AuctionSettled(_auction.auction_id, _auction.bidder, _auction.amount)

@internal
def _create_bid(auction_id: uint256, amount: uint256):
    _auction: Auction = self.auction_list[auction_id]

    assert _auction.auction_id == auction_id, "Invalid auction ID"
    assert block.timestamp < _auction.end_time, "Auction expired"
    assert amount >= self.reserve_price, "Must send at least reservePrice"
    assert amount >= _auction.amount + (
        (_auction.amount * self.min_bid_increment_percentage) // 100
    ), "Must send more than last bid by min_bid_increment_percentage amount"

    # If msg.value < amount, try to use pending returns for the remainder
    pending_amount: uint256 = self.pending_returns[msg.sender]
    tokens_needed: uint256 = amount
    
    if pending_amount > 0:
        if pending_amount >= amount:
            # Use pending returns only
            self.pending_returns[msg.sender] -= amount
            tokens_needed = 0
        else:
            # Use all pending returns plus some tokens
            self.pending_returns[msg.sender] = 0
            tokens_needed = amount - pending_amount

    # Transfer any additional tokens needed
    if tokens_needed > 0:
        assert extcall self.payment_token.transferFrom(msg.sender, self, tokens_needed), "Token transfer failed"

    last_bidder: address = _auction.bidder
    if last_bidder != empty(address):
        self.pending_returns[last_bidder] += _auction.amount

    extended: bool = _auction.end_time - block.timestamp < self.time_buffer
    self.auction_list[auction_id] = Auction(
        auction_id=_auction.auction_id,
        amount=amount,
        start_time=_auction.start_time,
        end_time=_auction.end_time if not extended else block.timestamp + self.time_buffer,
        bidder=msg.sender,
        settled=_auction.settled
    )

    log AuctionBid(_auction.auction_id, msg.sender, amount, extended)

    if extended:
        log AuctionExtended(_auction.auction_id, _auction.end_time)



@internal
def _pause():
    self.paused = True


@internal
def _unpause():
    self.paused = False
