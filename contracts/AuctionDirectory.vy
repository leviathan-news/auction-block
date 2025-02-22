# @version 0.4.0

"""
@title Auction Directory
@author https://github.com/leviathan-news/auction-block
@license MIT
@notice Central registry and interface for Leviathan auction system
@dev Core contract providing:
     - Unified bidding interface for all auction types
     - Multi-token support through zap contracts
     - Permission management for delegated bidding
     - Registry of all deployed auction contracts


                            ####++++++++
                       #+++++++++####+++##++
                     #########+++-++##++-..
                      ....++++#++++++#+++-....
                 ++++++----+++++++++++++++++-..-++##
                  ...-+++++++++++++++++++++++++++#####
              +++-....+#+++++++++++++++++++++++++######
          +++++++++++++++++++++++++++++++-+++++++++++++++++
        ++#########++++++++----+++--++----+++++++########++++
      ###############+++++-.-------------..+++++#############++
     ##########++++###++++.  .---------.  .+++++++++-+++  ######
     ########  ....--+++++.   .-------..  .++++++++++#+++#+ ####
    ########  ..--+++++++++....-------....+++++++####+++++## ###
     ######   +++++++++++++++-+-----+-++-+-++++++#######++++
     #####   +#######+#+++++++++-+-++-++++++++++++---+#####++
      ####  ++####+----+++++++++++++++++++++++++++++-  #####++
       ###  +###+.....-+++++++++++++++++++++++++###+++  +###++
            ++##+....-+++++#+++++++++++++#++++----+##++  +####+
            +###  ..-+#####++++++++++++++##+++-....##++   ####
            ++##   ++####+-++++##+##+++++++###++-+  +++  #####
             +##+  +####-..+++####++###++-.-+###+++ ++   ###
               +#  +####-..++#####--+###++--  +#++++
                   ++###   +++####+..-+###+++   ++++
                    ++#++   ++++###+     +#+++  +++
                     ++++     +++++++     +++++
                       +++      +++++++    +++
                                     ++    +
"""


# ============================================================================================
# ⚙️ Modules
# ============================================================================================

from ethereum.ercs import IERC20

from .imports import ownable_2step as ownable
from .imports import pausable


# ============================================================================================
# 🧩 Interfaces
# ============================================================================================

interface AuctionHouse:
    def current_auctions() -> DynArray[uint256, MAX_AUCTIONS]: view
    def create_bid(
        auction_id: uint256,
        bid_amount: uint256,
        ipfs_hash: String[46],
        on_behalf_of: address,
    ): nonpayable
    def minimum_total_bid(auction_id: uint256) -> uint256: view
    def minimum_additional_bid_for_user(
        auction_id: uint256, user: address
    ) -> uint256: view
    def auction_bid_by_user(auction_id: uint256, user: address) -> uint256: view
    def update_bid_metadata(
        auction_id: uint256, ipfs_hash: String[46], on_behalf_of: address
    ): nonpayable
    def withdraw(
        auction_id: uint256, on_behalf_of: address
    ) -> uint256: nonpayable
    def withdraw_multiple(
        auction_ids: DynArray[uint256, 100], on_behalf_of: address
    ): nonpayable


interface AuctionZap:
    def get_dy(dx: uint256) -> uint256: view
    def safe_get_dx(dy: uint256) -> uint256: view
    def zap(token_amount: uint256, min_dy: uint256) -> uint256: nonpayable


interface AuctionOracle:
    def price_usd() -> uint256: view


interface AuctionNFT:
    def safe_mint(
        owner: address, contract_address: address, auction_id: uint256
    ) -> uint256: nonpayable


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

struct AuctionInfo:
    contract_address: address
    auction_id: uint256


flag ApprovalStatus:
    Nothing  # Default value, indicating no approval
    BidOnly  # Approved for bid only
    WithdrawOnly  # Approved for withdraw only
    BidAndWithdraw  # Approved for both bid and withdraw


# ============================================================================================
# 📣 Events
# ============================================================================================

event AuctionHouseAdded:
    contract_address: indexed(address)


event DirectoryDeprecated:
    new_address: indexed(address)


event TokenSupportAdded:
    token: indexed(address)
    trader: indexed(address)


event TokenSupportRemoved:
    token: indexed(address)


event ApprovedCallerSet:
    account: address
    caller: address
    status: ApprovalStatus


# ============================================================================================
# 📜 Constants
# ============================================================================================

MAX_TOKENS: constant(uint256) = 100
MAX_AUCTION_CONTRACTS: constant(uint256) = 1000
MAX_AUCTIONS: constant(uint256) = 10000
MAX_WITHDRAWALS: constant(uint256) = 100


# ============================================================================================
# 💾 Storage
# ============================================================================================

# Is there a more recent version of this directory?
directory_is_current: public(bool)
directory_upgrade_address: public(address)

# Auction Contracts
registered_auction_contracts: public(
    DynArray[AuctionHouse, MAX_AUCTION_CONTRACTS]
)

# User settings: user -> caller -> status
approved_caller: public(HashMap[address, HashMap[address, ApprovalStatus]])

# Payment tokens
payment_token: public(IERC20)

# Other Supported Tokens
supported_tokens: public(DynArray[IERC20, MAX_TOKENS])
supported_token_zaps: public(HashMap[IERC20, AuctionZap])

# Optional price oracle
oracle: public(AuctionOracle)

# Optional NFT contract minted on settlement
nft: public(AuctionNFT)


# ============================================================================================
# 🚧 Constructor
# ============================================================================================

@deploy
def __init__(payment_token: IERC20):
    self.directory_is_current = True
    ownable.__init__()
    pausable.__init__()
    self.payment_token = payment_token


# ============================================================================================
# 👀 View functions
# ============================================================================================

@external
@view
def active_auctions() -> DynArray[AuctionInfo, MAX_AUCTIONS]:
    """
    @notice Returns all currently active auctions across all registered contracts
    @dev Iterates through all registered contracts and their current auctions
         Memory bounded by MAX_AUCTIONS constant
         Introduced for UI convenience
    @return Array of AuctionInfo structs containing contract addresses and auction IDs
    """
    auction_list: DynArray[AuctionInfo, MAX_AUCTIONS] = []

    for _contract: AuctionHouse in self.registered_auction_contracts:
        _current_auctions: DynArray[
            uint256, MAX_AUCTIONS
        ] = staticcall _contract.current_auctions()

        for _auction_id: uint256 in _current_auctions:
            auction_list.append(
                AuctionInfo(
                    contract_address=_contract.address, auction_id=_auction_id
                )
            )
    return auction_list


@external
@view
def safe_get_dx(token: IERC20, dy: uint256) -> uint256:
    """
    @notice Calculates the required input amount of alternate token for a desired bid
    @dev Uses zap contract's safe calculation which includes safety margin
         Gas inefficient, intended for offchain use
         Reverts if token not supported
    @param token The alternate token address to calculate for
    @param dy The desired output amount in payment tokens
    @return Required input amount of alternate token, including safety margin
    """

    assert self.supported_token_zaps[token] != empty(AuctionZap), "!token"
    return staticcall self.supported_token_zaps[token].safe_get_dx(dy)


@external
@view
def get_dy(token: IERC20, dx: uint256) -> uint256:
    """
    @notice Calculates expected output of payment tokens for a given alternate token input
    @dev Direct price quote from AuctionZap contract
    @param token The alternate token address to calculate for
    @param dx The input amount of alternate token
    @return Expected output amount in payment tokens
    """
    assert self.supported_token_zaps[token] != empty(AuctionZap), "!token"
    return staticcall self.supported_token_zaps[token].get_dy(dx)


@external
@view
def num_auction_contracts() -> uint256:
    """
    @notice Returns the total number of registered auction contracts
    @dev Helper function for UI pagination/iteration
    @return Current count of registered auction contracts
    """
    return len(self.registered_auction_contracts)


@external
@view
def num_supported_tokens() -> uint256:
    """
    @notice Returns the total number of registered token zaps
    @dev Helper function for UI pagination/iteration
    @return Current count of supported tokens
    """
    return len(self.supported_tokens)


@external
@view
def payment_token_price_usd() -> uint256:
    """
    @notice Returns current price of payment token in USD
    @dev Implemented for indicative UI display
    @return Price in 18 decimals
    """
    return staticcall self.oracle.price_usd()


# ============================================================================================
# ✍️ Write functions
# ============================================================================================

@external
@nonreentrant
def create_bid(
    auction_contract: AuctionHouse,
    auction_id: uint256,
    bid_amount: uint256,
    ipfs_hash: String[46] = "",
    on_behalf_of: address = msg.sender,
):
    """
    @notice Place a bid on an auction using the primary payment token
    @dev Transfers tokens from bidder to directory, then executes bid on auction contract
         Caller must have approval status or be bidding for themselves
    @param auction_contract The target auction contract address
    @param auction_id The ID of the auction to bid on
    @param bid_amount Total bid amount in payment tokens
    @param ipfs_hash Optional IPFS hash for bid metadata
    @param on_behalf_of Address to place bid for (defaults to caller)
    @custom:security Requires auction contract to be registered and appropriate approval for delegated bids
                     Requires appropriate approval status for delegated bids
    """
    pausable._check_unpaused()
    assert self._is_registered_contract(auction_contract), "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)

    # Calculate transfer amount
    _current_bid: uint256 = staticcall auction_contract.auction_bid_by_user(
        auction_id, on_behalf_of
    )
    _transfer_amount: uint256 = bid_amount
    if _current_bid > 0:
        _transfer_amount = bid_amount - _current_bid

    extcall self.payment_token.transferFrom(
        on_behalf_of, self, _transfer_amount
    )

    # Create bid
    extcall self.payment_token.approve(
        auction_contract.address, _transfer_amount
    )
    extcall auction_contract.create_bid(
        auction_id, bid_amount, ipfs_hash, on_behalf_of
    )


@external
@nonreentrant
def create_bid_with_token(
    auction_contract: AuctionHouse,
    auction_id: uint256,
    token_amount: uint256,
    token: IERC20,
    min_total_bid: uint256,
    ipfs_hash: String[46] = "",
    on_behalf_of: address = msg.sender,
):
    """
    @notice Place a bid using an alternative token that gets swapped to the payment token
    @dev Transfers alternate tokens from bidder, executes swap via zap contract, then places bid
         Must approve directory for alternate token
    @param auction_contract The target auction contract
    @param auction_id ID of the auction to bid on
    @param token_amount Amount of alternate token to swap and bid with
    @param token Address of the alternate token (must be supported)
    @param min_total_bid Minimum acceptable total bid after token conversion
    @param ipfs_hash Optional IPFS hash for bid metadata
    @param on_behalf_of Address to place bid for (defaults to caller)
    @custom:security Requires auction contract to be registered
                     Requires token to have zap contract configured
                     Requires appropriate approval status for delegated bids
    """
    pausable._check_unpaused()
    assert self._is_registered_contract(auction_contract), "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)

    # Check if token trading is authorized
    auction_zap: AuctionZap = self.supported_token_zaps[token]
    assert auction_zap != empty(AuctionZap), "!token"

    # Did the user request enough tokens?
    current_bid: uint256 = staticcall auction_contract.auction_bid_by_user(
        auction_id, on_behalf_of
    )
    min_requirement: uint256 = staticcall auction_contract.minimum_total_bid(
        auction_id
    )
    assert min_total_bid >= min_requirement, "!bid_amount"

    # Confirm output is sufficient
    expected_swap_output: uint256 = staticcall auction_zap.get_dy(token_amount)
    expected_total_bid: uint256 = current_bid + expected_swap_output
    assert expected_total_bid >= min_total_bid, "!token_amount"

    # Get tokens from user and zap
    extcall token.transferFrom(on_behalf_of, self, token_amount)
    extcall token.approve(auction_zap.address, token_amount)
    received: uint256 = extcall auction_zap.zap(
        token_amount, expected_swap_output
    )

    # Place bid with received tokens
    extcall self.payment_token.approve(auction_contract.address, received)
    extcall auction_contract.create_bid(
        auction_id, received + current_bid, ipfs_hash, on_behalf_of
    )


@external
def set_approved_caller(caller: address, status: ApprovalStatus):
    """
    @notice Configure delegation permissions for a specific caller
    @dev Allows user to set granular permissions for another address
    @param caller Address being granted or restricted permissions
    @param status Approval level for the caller:
                  - Nothing: No permissions
                  - BidOnly: Can place bids on behalf of user
                  - WithdrawOnly: Can withdraw funds on behalf of user
                  - BidAndWithdraw: Full bidding and withdrawal permissions
    """
    self.approved_caller[msg.sender][caller] = status
    log ApprovedCallerSet(msg.sender, caller, status)


@external
def mint_nft(target: address, auction_id: uint256) -> uint256:
    """
    @notice Mint NFT or fail gracefully
    @dev Called by AuctionBlock on settlement, so revert would prevent settlement.
         Set nft to null address to bypass
    @param target Address to mint the NFT to
    @param auction_id Auction ID that won the NFT
    @return 0 on fail or NFT id
    """
    _token_id: uint256 = 0
    _is_registered: bool = self._is_registered_contract(
        AuctionHouse(msg.sender)
    )

    # Check if NFT address is set and called by and for an authorized contract
    if self.nft.address != empty(address) and _is_registered:

        # OK to mint
        _token_id = extcall self.nft.safe_mint(target, msg.sender, auction_id)

    return _token_id


@external
@nonreentrant
def update_bid_metadata(
    auction_contract: AuctionHouse,
    auction_id: uint256,
    ipfs_hash: String[46],
    on_behalf_of: address = msg.sender,
):
    """
    @notice Update IPFS metadata associated with a user's bid
    @dev Allows adding or updating metadata for any bid by user
         Does not affect bid status or amount
    @param auction_contract The target auction contract address
    @param auction_id The auction to update metadata for
    @param ipfs_hash New IPFS hash to associate with bid
    @param on_behalf_of Address to update metadata for (defaults to caller)
    @custom:security Requires bid permission for on_behalf_of
                     OK while contract is paused
    """
    assert self._is_registered_contract(auction_contract), "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    extcall auction_contract.update_bid_metadata(
        auction_id, ipfs_hash, on_behalf_of
    )


@external
@nonreentrant
def withdraw(
    auction_contract: AuctionHouse,
    auction_id: uint256,
    on_behalf_of: address = msg.sender,
) -> uint256:
    """
    @notice Withdraw pending returns from previous outbid
    @dev Only available after auction is settled
         Clears pending returns for auction/user combination
    @param auction_contract The target auction contract address
    @param auction_id Auction to withdraw from
    @param on_behalf_of Address to withdraw for (defaults to caller)
    @return Amount of tokens withdrawn
    @custom:security Requires withdraw permission for on_behalf_of
                     Only withdraws if auction is settled
    """
    pausable._check_unpaused()
    assert self._is_registered_contract(auction_contract), "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.WithdrawOnly)
    return extcall auction_contract.withdraw(auction_id, on_behalf_of)


@external
@nonreentrant
def withdraw_multiple(
    auction_contract: AuctionHouse,
    auction_ids: DynArray[uint256, MAX_WITHDRAWALS],
    on_behalf_of: address = msg.sender,
):
    """
    @notice Batch withdraw pending returns from multiple auctions
    @dev Only withdraws from settled auctions
         Skips live auctions and non-settled auctions
    @param auction_ids Array of auction IDs to withdraw from
    @param on_behalf_of Address to withdraw for (defaults to caller)
    @custom:security Requires withdraw permission for on_behalf_of
                     Only processes settled auctions
                     Limited to MAX_WITHDRAWALS auctions
    """
    pausable._check_unpaused()
    assert self._is_registered_contract(auction_contract), "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.WithdrawOnly)
    extcall auction_contract.withdraw_multiple(auction_ids, on_behalf_of)


# ============================================================================================
# 👑 Owner functions
# ============================================================================================


@external
def register_auction_contract(new_auction_addr: AuctionHouse):
    """
    @notice Registers a new auction contract implementation
    @dev Only callable by owner
         New contract must implement AuctionHouse interface
    @param new_auction_addr Address of auction contract to register
    @custom:security Ensure contract is fully configured before registering
    """
    self.registered_auction_contracts.append(new_auction_addr)
    log AuctionHouseAdded(new_auction_addr.address)


@external
def deprecate_directory(new_directory_addr: address):
    """
    @notice Marks this directory as deprecated in favor of new implementation
    @dev Only callable by owner
         Sets directory_is_current to False and stores upgrade address
    @param new_directory_addr Address of new directory implementation
    @custom:security Users should migrate to new directory after deprecation
    """
    ownable._check_owner()
    self.directory_is_current = False
    self.directory_upgrade_address = new_directory_addr
    log DirectoryDeprecated(new_directory_addr)


@external
def set_nft(new_nft_addr: address):
    """
    @notice Updates the NFT contract
    @dev Set to zero address to disable NFT minting
    @param new_nft_addr Address of NFT contract
    """
    ownable._check_owner()
    self.nft = AuctionNFT(new_nft_addr)


@external
def add_token_support(new_token_addr: IERC20, new_zap_addr: AuctionZap):
    """
    @notice Adds support for a new alternate payment token
    @dev Only callable by owner
         Configures token with corresponding zap contract for AMM integration
    @param new_token_addr Address of alternate token to support
    @param new_zap_addr Address of zap contract that handles token conversion
    @custom:security Zap contract must be verified and tested before adding
                     Cannot add primary payment token as alternate token
    """
    ownable._check_owner()
    assert new_zap_addr.address != empty(address), "!trader"
    assert new_token_addr.address != empty(address), "!token"
    assert new_token_addr != self.payment_token, "!payment_token"

    self.supported_token_zaps[new_token_addr] = new_zap_addr
    self.supported_tokens.append(new_token_addr)

    log TokenSupportAdded(new_token_addr.address, new_zap_addr.address)


@external
def revoke_token_support(token_addr: IERC20):
    """
    @notice Remove support for an alternative payment token
    @dev Only owner
    @param token_addr Address of previously supported token to remove
    """
    ownable._check_owner()
    assert token_addr.address != empty(address), "!token"
    assert self.supported_token_zaps[token_addr] != empty(
        AuctionZap
    ), "!supported"
    self.supported_token_zaps[token_addr] = empty(AuctionZap)

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
def set_payment_token_oracle(new_oracle_addr: AuctionOracle):
    """
    @notice Sets optional payment token oracle
    @dev Introduced for UI convenience, not intended for robust onchain calculations
    @param new_oracle_addr Contract with public `price_usd` function
    """

    ownable._check_owner()
    self.oracle = new_oracle_addr


@external
def recover_erc20(token_addr: address, amount: uint256):
    """
    @notice Recover ERC20 tokens accidentally sent to contract
    @dev Only callable by owner for cleanup purposes
    @param token_addr The token contract address
    @param amount Amount of tokens to recover
    """
    ownable._check_owner()
    token: IERC20 = IERC20(token_addr)

    assert extcall token.transfer(ownable.owner, amount), "transfer failed"


# ============================================================================================
# 🏠 Internal functions
# ============================================================================================

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


@internal
@view
def _is_registered_contract(contract_to_check: AuctionHouse) -> bool:
    _found_contract: bool = False
    for _contract: AuctionHouse in self.registered_auction_contracts:
        if contract_to_check == _contract:
            _found_contract = True
    return _found_contract
