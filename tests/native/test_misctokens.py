import boa
import pytest


def empty_address():
    return "0x0000000000000000000000000000000000000000"


def load_supported_tokens(house):
    ret_arr = []
    for i in range(10):
        try:
            ret_arr.append(house.supported_tokens(i))
        except Exception as e:
            print(f"Error {e} on {i}")
    print(ret_arr)
    return ret_arr


def test_add_token_support(auction_house, deployer, payment_token, inert_weth, inert_weth_trader):
    weth = inert_weth
    weth_trader = inert_weth_trader

    with boa.env.prank(deployer):
        # Initially, no supported tokens
        initial_tokens = load_supported_tokens(auction_house)
        assert len(initial_tokens) == 0

        # Add first token (WETH)
        auction_house.add_token_support(weth, weth_trader)

        # Check supported tokens after first addition
        tokens_after_first = load_supported_tokens(auction_house)
        assert len(tokens_after_first) == 1
        assert tokens_after_first[0] == weth.address

        # Try adding a second token
        test_token_contract = boa.load_partial("contracts/test/ERC20.vy")
        test_token = test_token_contract.deploy("Test", "TEST", 18)

        auction_house.add_token_support(test_token, boa.env.generate_address())

        # Check supported tokens after second addition
        tokens_after_second = load_supported_tokens(auction_house)

        assert len(tokens_after_second) == 2
        assert tokens_after_second[0] == weth.address
        assert tokens_after_second[1] == test_token.address


def test_cannot_add_payment_token(auction_house, payment_token, deployer):

    with boa.env.prank(deployer), boa.reverts("!payment_token"):
        auction_house.add_token_support(payment_token, boa.env.generate_address())


def test_revoke_token_support(
    auction_house, deployer, payment_token, inert_weth, inert_weth_trader
):
    weth_token = boa.load_partial("contracts/test/ERC20.vy").deploy("Wrapped ETH", "WETH", 18)
    weth_trader = boa.env.generate_address()

    with boa.env.prank(deployer):
        # Add multiple tokens
        auction_house.add_token_support(weth_token, weth_trader)

        test_token_contract = boa.load_partial("contracts/test/ERC20.vy")
        test_token = test_token_contract.deploy("Test Token", "TEST", 18)
        auction_house.add_token_support(test_token, boa.env.generate_address())

        # Initial state check
        tokens_before = load_supported_tokens(auction_house)
        assert len(tokens_before) == 2
        assert tokens_before[0] == weth_token.address
        assert tokens_before[1] == test_token.address

        # Revoke first token (WETH)
        auction_house.revoke_token_support(weth_token)

        # Check supported tokens after first removal
        tokens_after_first_removal = load_supported_tokens(auction_house)
        assert len(tokens_after_first_removal) == 1
        assert tokens_after_first_removal[0] == test_token.address

        # Revoke the remaining token
        auction_house.revoke_token_support(test_token)

        # Check supported tokens after second removal
        tokens_after_second_removal = load_supported_tokens(auction_house)
        assert len(tokens_after_second_removal) == 0


def test_revoke_token_support_order_preservation(auction_house, deployer, payment_token):
    with boa.env.prank(deployer):
        # Deploy test tokens
        weth_token = boa.load_partial("contracts/test/ERC20.vy").deploy("Wrapped ETH", "WETH", 18)
        test_token_1 = boa.load_partial("contracts/test/ERC20.vy").deploy("Test 1", "TEST1", 18)
        test_token_2 = boa.load_partial("contracts/test/ERC20.vy").deploy("Test 2", "TEST2", 18)

        # Add tokens
        auction_house.add_token_support(weth_token, boa.env.generate_address())
        auction_house.add_token_support(test_token_1, boa.env.generate_address())
        auction_house.add_token_support(test_token_2, boa.env.generate_address())

        # Initial state check
        tokens_before = load_supported_tokens(auction_house)
        assert len(tokens_before) == 3
        assert tokens_before[0] == weth_token.address
        assert tokens_before[1] == test_token_1.address
        assert tokens_before[2] == test_token_2.address

        # Remove middle token (test_token_1)
        auction_house.revoke_token_support(test_token_1)

        # Check order preservation
        tokens_after_removal = load_supported_tokens(auction_house)
        assert len(tokens_after_removal) == 2
        assert tokens_after_removal[0] == weth_token.address
        assert tokens_after_removal[1] == test_token_2.address


def test_add_token_support_error_handling(auction_house, deployer):
    with boa.env.prank(deployer):
        # Attempt to add empty address should revert
        with boa.reverts("!token"):
            auction_house.add_token_support(empty_address(), boa.env.generate_address())

        # Attempt to add token without trader should revert
        test_token = boa.load_partial("contracts/test/ERC20.vy").deploy("Test", "TEST", 18)
        with boa.reverts("!trader"):
            auction_house.add_token_support(test_token, empty_address())


def test_revoke_token_support_error_handling(auction_house, deployer):
    # Attempt to revoke unsupported token should revert
    test_token = boa.load_partial("contracts/test/ERC20.vy").deploy("Test", "TEST", 18)

    with boa.env.prank(deployer):
        # Attempt to revoke unsupported token should revert
        with boa.reverts("!supported"):
            auction_house.revoke_token_support(test_token)

        # Attempt to revoke with empty address should revert
        with boa.reverts("!token"):
            auction_house.revoke_token_support(empty_address())
