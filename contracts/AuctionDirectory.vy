# @version 0.4.0

"""
@title Auction Directory
@author Leviathan News
@license MIT
@notice Central registry and interface for Leviathan auction system
@dev Core contract providing:
     - Unified bidding interface for all auction types
     - Multi-token support through zap contracts
     - Permission management for delegated bidding
     - Registry of all deployed auction contracts
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

interface AuctionContract:
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


interface NFT:
    def safe_mint(
        owner: address, contract_address: address, auction_id: uint256
    ) -> int256: nonpayable


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

event AuctionContractAdded:
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

# Is there a more recent version of this diretory?
is_current: public(bool)
upgrade_address: public(address)

# Auction Contracts
registered_contracts: public(DynArray[AuctionContract, MAX_AUCTION_CONTRACTS])

# User settings: user -> caller -> status
approved_caller: public(HashMap[address, HashMap[address, ApprovalStatus]])

# Payment tokens
payment_token: public(IERC20)
additional_tokens: public(HashMap[IERC20, AuctionZap])
supported_tokens: public(DynArray[IERC20, MAX_TOKENS])
nft: public(NFT)


# ============================================================================================
# 🚧 Constructor
# ============================================================================================

@deploy
def __init__(payment_token: IERC20):
    self.is_current = True
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
    @return Array of AuctionInfo structs containing contract addresses and auction IDs
    """
    auction_list: DynArray[AuctionInfo, MAX_AUCTIONS] = []

    for _contract: AuctionContract in self.registered_contracts:
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
         Reverts if token not supported
    @param token The alternate token address to calculate for
    @param dy The desired output amount in payment tokens
    @return Required input amount of alternate token, including safety margin
    """

    assert self.additional_tokens[token] != empty(AuctionZap), "!token"
    return staticcall self.additional_tokens[token].safe_get_dx(dy)


@external
@view
def get_dy(token: IERC20, dx: uint256) -> uint256:
    """
    @notice Calculates expected output of payment tokens for a given alternate token input
    @dev Direct price quote without safety margin, use safe_get_dx for actual bidding
    @param token The alternate token address to calculate for
    @param dx The input amount of alternate token
    @return Expected output amount in payment tokens
    """
    assert self.additional_tokens[token] != empty(AuctionZap), "!token"
    return staticcall self.additional_tokens[token].get_dy(dx)


@external
@view
def num_auction_contracts() -> uint256:
    """
    @notice Returns the total number of registered auction contracts
    @dev Helper function for UI pagination/iteration
    @return Current count of registered auction contracts
    """
    return len(self.registered_contracts)


@external
@view
def num_supported_tokens() -> uint256:
    """
    @notice Returns the total number of registered token zaps
    @dev Helper function for UI pagination/iteration
    @return Current count of supported tokens
    """
    return len(self.supported_tokens)


# ============================================================================================
# ✍️ Write functions
# ============================================================================================


@external
@nonreentrant
def create_bid(
    auction_contract: AuctionContract,
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

    # Get tokens from user
    _transfer_amount: uint256 = (
        staticcall auction_contract.minimum_additional_bid_for_user(
            auction_id, on_behalf_of
        )
    )
    extcall self.payment_token.transferFrom(
        on_behalf_of, self, _transfer_amount
    )
    extcall self.payment_token.approve(
        auction_contract.address, _transfer_amount
    )
    extcall auction_contract.create_bid(
        auction_id, bid_amount, ipfs_hash, on_behalf_of
    )


@external
@nonreentrant
def create_bid_with_token(
    auction_contract: AuctionContract,
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
         Must approve both Directory for alternate token and auction for payment token
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
    # Contract exists
    assert self._is_registered_contract(auction_contract), "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)

    # Token trading authorized
    auction_zap: AuctionZap = self.additional_tokens[token]
    assert auction_zap != empty(AuctionZap), "!token"

    # Did the user request enough tokens?
    current_bid: uint256 = staticcall auction_contract.auction_bid_by_user(
        auction_id, on_behalf_of
    )
    assert current_bid < min_total_bid, "!bid_amount"

    # Is the user's bid sufficient
    assert min_total_bid >= staticcall auction_contract.minimum_total_bid(
        auction_id
    ), "!bid_amount"

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
def mint_nft(
    target: address, auction_id: uint256, contract_addr: address = msg.sender
) -> int256:
    """
    @notice Mint NFT or fail gracefully
    @param target Address to mint the NFT to
    @param auction_id Auction ID that won the NFT
    @return -1 on fail or NFT id
    """
    token_id: int256 = -1
    if self._is_registered_contract(
        AuctionContract(contract_addr)
    ) and self.nft.address != empty(address):
        token_id = extcall self.nft.safe_mint(target, contract_addr, auction_id)
    return token_id


@external
@nonreentrant
def update_bid_metadata(
    auction_contract: AuctionContract,
    auction_id: uint256,
    ipfs_hash: String[46],
    on_behalf_of: address,
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
    """
    assert self._is_registered_contract(auction_contract), "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    extcall auction_contract.update_bid_metadata(
        auction_id, ipfs_hash, on_behalf_of
    )


@external
@nonreentrant
def withdraw(
    auction_contract: AuctionContract,
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
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    return extcall auction_contract.withdraw(auction_id, on_behalf_of)


@external
@nonreentrant
def withdraw_multiple(
    auction_contract: AuctionContract,
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
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    extcall auction_contract.withdraw_multiple(auction_ids, on_behalf_of)


# ============================================================================================
# 👑 Owner functions
# ============================================================================================


@external
def register_auction_contract(new_contract: AuctionContract):
    """
    @notice Registers a new auction contract implementation
    @dev Only callable by owner
         New contract must implement AuctionContract interface
    @param new_contract Address of auction contract to register
    @custom:security Ensure contract is fully configured before registering
    """
    self.registered_contracts.append(new_contract)
    log AuctionContractAdded(new_contract.address)


@external
def deprecate_directory(new_address: address):
    """
    @notice Marks this directory as deprecated in favor of new implementation
    @dev Only callable by owner
         Sets is_current to False and stores upgrade address
    @param new_address Address of new directory implementation
    @custom:security Users should migrate to new directory after deprecation
    """
    ownable._check_owner()
    self.is_current = False
    self.upgrade_address = new_address
    log DirectoryDeprecated(new_address)


@external
def set_nft(nft_addr: address):
    """
    @notice Updates the NFT contract
    @dev Set to zero address to disable NFT minting
    @param nft_addr Address of NFT contract
    """
    ownable._check_owner()
    self.nft = NFT(nft_addr)


@external
def add_token_support(token: IERC20, zap_address: AuctionZap):
    """
    @notice Adds support for a new alternate payment token
    @dev Only callable by owner
         Configures token with corresponding zap contract for AMM integration
    @param token Address of alternate token to support
    @param zap_address Address of zap contract that handles token conversion
    @custom:security Zap contract must be verified and tested before adding
                     Cannot add primary payment token as alternate token
    """

    ownable._check_owner()
    assert token.address != empty(address), "!token"
    assert zap_address.address != empty(address), "!trader"
    assert token != self.payment_token, "!payment_token"

    self.additional_tokens[token] = zap_address
    self.supported_tokens.append(token)
    log TokenSupportAdded(token.address, zap_address.address)


@external
def revoke_token_support(token_addr: IERC20):
    """
    @notice Remove support for an alternative payment token
    @dev Only owner
    @param token_addr Address of previously supported token to remove
    """
    ownable._check_owner()
    assert token_addr.address != empty(address), "!token"
    assert self.additional_tokens[token_addr] != empty(AuctionZap), "!supported"
    self.additional_tokens[token_addr] = empty(AuctionZap)

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
def _is_registered_contract(contract_to_check: AuctionContract) -> bool:
    _found_contract: bool = False
    for _contract: AuctionContract in self.registered_contracts:
        if contract_to_check == _contract:
            _found_contract = True
    return _found_contract
