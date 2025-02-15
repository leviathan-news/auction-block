# @version 0.4.0

"""
@title Auction Directory
@license MIT
@author Leviathan
@notice Registry to list permutations of auction contracts
"""

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
    def create_bid_with_token(
        auction_id: uint256,
        token_amount: uint256,
        token: IERC20,
        min_dy: uint256,
        ipfs_hash: String[46],
        on_behalf_of: address,
    ): nonpayable


interface TokenTrader:
    def exchange(
        _dx: uint256, _min_dy: uint256, _from: address = msg.sender
    ) -> uint256: nonpayable
    def safe_get_dx(_dy: uint256) -> uint256: view
    def get_dx(_dy: uint256) -> uint256: view
    def get_dy(_dx: uint256) -> uint256: view


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


# ============================================================================================
# 💾 Storage
# ============================================================================================

# Is there a more recent version of this diretory?
is_current: public(bool)
upgrade_address: public(address)

# Auction Contracts
registered_contracts: public(DynArray[AuctionContract, MAX_AUCTION_CONTRACTS])

# User settings
approved_caller: public(HashMap[address, HashMap[address, ApprovalStatus]])

# Payment tokens
payment_token: public(IERC20)
additional_tokens: public(HashMap[IERC20, TokenTrader])
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
    @dev Returns a list of tuples where each tuple contains an auction contract address
         and an active auction ID.
    @return A single flat list of (contract address, auction ID) pairs.
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
    return staticcall self.additional_tokens[_token_addr].safe_get_dx(_dy)


@external
@view
def num_contracts() -> uint256:
    return len(self.registered_contracts)


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
    @dev Create a bid using the primary payment token
    """
    pausable._check_unpaused()
    assert auction_contract in self.registered_contracts, "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)

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
    min_dy: uint256,
    ipfs_hash: String[46] = "",
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
    pausable._check_unpaused()
    assert auction_contract in self.registered_contracts, "!contract"
    self._check_caller(on_behalf_of, msg.sender, ApprovalStatus.BidOnly)
    extcall auction_contract.create_bid_with_token(
        auction_id, token_amount, token, min_dy, ipfs_hash, on_behalf_of
    )


@external
def set_approved_caller(caller: address, status: ApprovalStatus):
    """
    @dev Set approval status for a caller
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
    # assert self._is_registered_contract(msg.sender), "!registered"
    token_id: int256 = -1
    if self._is_registered_contract(
        contract_addr
    ) and self.nft.address != empty(address):
        token_id = extcall self.nft.safe_mint(target, contract_addr, auction_id)
    return token_id


# ============================================================================================
# 👑 Owner functions
# ============================================================================================


@external
def register_auction_contract(new_contract: AuctionContract):
    self.registered_contracts.append(new_contract)
    log AuctionContractAdded(new_contract.address)


@external
def deprecate_directory(new_address: address):
    ownable._check_owner()
    self.is_current = False
    self.upgrade_address = new_address
    log DirectoryDeprecated(new_address)


@external
def set_nft(nft_addr: address):
    ownable._check_owner()
    self.nft = NFT(nft_addr)


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
def _is_registered_contract(contract_address: address) -> bool:
    _found_contract: bool = False
    for _contract: AuctionContract in self.registered_contracts:
        if contract_address == _contract.address:
            _found_contract = True
    return _found_contract
