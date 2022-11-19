# @version ^0.3.7

# ERC20 Interface
@view
@external
def balanceOf(account: address) -> uint256:
    """
    @notice Get the balance of an account
    """
    return 0


@view
@external
def allowance(owner: address, spender: address) -> uint256:
    """
    @notice Get the allowance granted by an owner to a spender
    """
    return 0


@external
def approve(spender: address, amount: uint256) -> bool:
    """
    @notice Approve a spender to transfer tokens
    """
    return True


@external
def transfer(recipient: address, amount: uint256) -> bool:
    """
    @notice Transfer tokens to an address
    """
    return True


@external
def transferFrom(sender: address, recipient: address, amount: uint256) -> bool:
    """
    @notice Transfer tokens from one address to another
    """
    return True


# WETH-specific functions
@external
@payable
def deposit():
    """
    @notice Deposit ETH for WETH
    """
    pass


@external
def withdraw(amount: uint256):
    """
    @notice Withdraw ETH by burning WETH
    """
    pass
