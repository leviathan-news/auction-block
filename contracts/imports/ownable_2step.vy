# @version 0.4.0

"""
@title Ownable 2-step
@license MIT
@author yearn.finance, asymmetry.finance
@notice ownable_2step.vy is a two-step ownable contract that allows for a two-step transfer of ownership
"""


# ============================================================================================
# Events
# ============================================================================================


event PendingOwnershipTransfer:
    old_owner: address
    new_owner: address


event OwnershipTransferred:
    old_owner: address
    new_owner: address


# ============================================================================================
# Storage
# ============================================================================================


owner: public(address)
pending_owner: public(address)


# ============================================================================================
# Constructor
# ============================================================================================


@deploy
@payable
def __init__():
    """
    @dev To omit the opcodes for checking the `msg.value`
         in the creation-time EVM bytecode, the constructor
         is declared as `payable`.
    @notice Initializes the contract setting the deployer as the initial owner
    """
    self.owner = msg.sender


# ============================================================================================
# Owner functions
# ============================================================================================


@external
def transfer_ownership(new_owner: address):
    """
    @dev Starts the ownership transfer of the contract
         to a new account `new_owner`
    @notice Note that this function can only be
            called by the current `owner`. Also, there is
            no security risk in setting `new_owner` to the
            zero address as the default value of `pending_owner`
            is in fact already the zero address and the zero
            address cannot call `accept_ownership`. Eventually,
            the function replaces the pending transfer if
            there is one
    @param new_owner The address of the new owner
    """
    self._check_owner()
    self.pending_owner = new_owner
    log PendingOwnershipTransfer(self.owner, new_owner)


@external
def accept_ownership():
    """
    @dev The new owner accepts the ownership transfer.
    @notice Note that this function can only be
            called by the current `pending_owner`
    """
    assert self.pending_owner == msg.sender, "!new owner"
    self._transfer_ownership(msg.sender)


# ============================================================================================
# Internal functions
# ============================================================================================


@internal
def _check_owner():
    """
    @dev Throws if the sender is not the owner
    """
    assert msg.sender == self.owner, "!owner"


@internal
def _transfer_ownership(new_owner: address):
    """
    @dev Transfers the ownership of the contract
         to a new account `new_owner` and deletes
         any pending owner
    @notice This is an `internal` function without
            access restriction
    @param new_owner The address of the new owner
    """
    self.pending_owner = empty(address)
    old_owner: address = self.owner
    self.owner = new_owner
    log OwnershipTransferred(old_owner, new_owner)
