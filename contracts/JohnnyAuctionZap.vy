# @version 0.4.0

# @notice WETH Auction Zap
# @dev Trade WETH -> SQUID through Curve pool
# @author Leviathan
# @license MIT

from ethereum.ercs import IERC20

# ============================================================================================
# 🧩 Interfaces
# ============================================================================================

interface Pool:
    def exchange(
        i: uint256,
        j: uint256,
        dx: uint256,
        min_dy: uint256,
    ) -> uint256: nonpayable


interface AuctionBlock:
    def create_bid(
        auction_id: uint256,
        bid_amount: uint256,
        ipfs_hash: String[46],
        on_behalf_of: address,
    ): nonpayable

# ============================================================================================
# 💾 Storage
# ============================================================================================

payment_token: public(IERC20)
trading_token: public(IERC20)
pool: public(Pool)
indices: public(uint256[2])

# user --> caller --> is_approved
approved_caller: public(HashMap[address, HashMap[address, bool]]) # @note -- create a setter

# ============================================================================================
# 🚧 Constructor
# ============================================================================================


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

# ============================================================================================
# ✍️ Write functions
# ============================================================================================

# @note: user needs to approve this contract as an approved bidder on the auctionDirectory
# @note #2: user can approve the bot to `zap_and_bid` on his behalf, either by updating `approved_caller` on this contract, or updating the whole approve_call functionality in the directory and coordinate through there (latter options probably opens a rug vector if we can update the zap in the dir)
@external
def zap_and_bid(
    auction_contract: AuctionBlock,
    auction_id: uint256,
    token_amount: uint256,
    min_amount_out: uint256,
    ipfs_hash: String[46] = "",
    on_behalf_of: address = msg.sender,
):
    """
    @notice Create a bid using an alternative token
    @dev Must have approved the token for use with this contract
    @param auction_id An active auction
    @param token_amount Quantity of misc token to trade.  Value should exclude any existing bid amount
    @param min_amount_out Required minimum SQUID amount after the swap, or revert (slippage)
    @param on_behalf_of User to bid on behalf of
    @param ipfs_hash Optional data to register with the bid
    """
    if msg.sender != on_behalf_of:
        assert self.approved_caller[on_behalf_of][msg.sender], "!approved"

    amount_received: uint256 = self._exchange(token_amount)
    assert amount_received >= min_amount_out, "!token_amount"

    extcall auction_contract.create_bid(
        auction_id, amount_received, ipfs_hash, on_behalf_of
    )


# ============================================================================================
# 🏠 Internal functions
# ============================================================================================

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