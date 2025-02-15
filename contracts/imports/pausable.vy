# @version 0.4.0

"""
@title Pausable
@license MIT
@author Leviathan
@notice pauseable.vy allows to implement an emergency stop mechanism that can be triggered by an authorized account
"""

import ownable_2step as ownable


# ============================================================================================
# Modules
# ============================================================================================


uses: ownable


# ============================================================================================
# Events
# ============================================================================================


event Paused:
    account: address


event Unpaused:
    account: address


# ============================================================================================
# Storage
# ============================================================================================


paused: public(bool)


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
    @notice At initialisation time, the `owner` role will
            be assigned to the `msg.sender` since we `uses`
            the `ownable` module, which implements the
            aforementioned logic at contract creation time.
    """
    pass


# ============================================================================================
# Owner functions
# ============================================================================================


@external
def pause():
    """
    @dev Pauses the contract
    """
    ownable._check_owner()
    self._check_unpaused()
    self.paused = True
    log Paused(msg.sender)


@external
def unpause():
    """
    @dev Unpauses the contract
    """
    ownable._check_owner()
    self._check_paused()
    self.paused = False
    log Unpaused(msg.sender)


# ============================================================================================
# Internal functions
# ============================================================================================


@internal
def _check_unpaused():
    """
    @dev Checks if the contract is unpaused
    """
    assert not self.paused, "paused"


@internal
def _check_paused():
    """
    @dev Checks if the contract is paused
    """
    assert self.paused, "!paused"
