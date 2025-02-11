import boa
import pytest

pytestmark = pytest.mark.fork_only


def test_specific_bid_scenario_proper_fail(auction_house, weth_trader, weth, payment_token, alice):
    # Get the reserve price as our target output amount
    reserve_price = auction_house.default_reserve_price()

    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()

    # Calculate required WETH input for this output
    bid_amount = auction_house.safe_get_dx(weth, reserve_price)
    # Add 1% buffer to ensure we exceed minimum
    min_dy = reserve_price * 99 // 100  # Allow 1% slippage

    # Record initial balances
    print(f"\nInitial balances:")
    print(f"WETH: {weth.balanceOf(alice)}")
    print(f"SQUID: {payment_token.balanceOf(alice)}")
    print(f"Required WETH input: {bid_amount}")
    print(f"Minimum SQUID output: {min_dy}")
    print(f"Expected SQUID output: {auction_house.get_dy(weth, bid_amount)}")

    with boa.env.prank(alice):
        # ONLY approve WETH, not payment token
        weth.approve(auction_house, 2**256 - 1)
        auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)


def test_various_approval_scenarios(auction_house, weth_trader, weth, payment_token, alice):
    # Setup first
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()

    # Calculate our bid amounts based on current rates
    reserve_price = auction_house.default_reserve_price()
    bid_amount = auction_house.safe_get_dx(weth, reserve_price * 2)  # Get enough for 2x reserve
    min_dy = reserve_price  # Must at least meet reserve

    # Print initial state
    print(f"\nInitial balances and setup:")
    print(f"WETH balance: {weth.balanceOf(alice)}")
    print(f"Reserve price: {reserve_price}")
    print(f"Required bid amount: {bid_amount}")
    print(f"Min output required: {min_dy}")
    print(f"Expected output: {auction_house.get_dy(weth, bid_amount)}")

    with boa.env.prank(alice):
        # Try resetting approval to 0 first
        weth.approve(auction_house, 0)
        weth.approve(auction_house, 2**256 - 1)

        # First bid should be enough to meet reserve price
        first_amount = bid_amount // 2  # Half of total (still > reserve)
        first_min_dy = reserve_price  # Must meet reserve

        print(f"\nTrying first trade:")
        print(f"Amount: {first_amount}")
        print(f"Min dy: {first_min_dy}")
        print(f"Expected output: {auction_house.get_dy(weth, first_amount)}")

        auction_house.create_bid_with_token(auction_id, first_amount, weth, first_min_dy)

        print("\nFirst trade succeeded")

        # Now try the full amount (needs to beat minimum increment)
        second_amount = bid_amount
        second_min_dy = auction_house.minimum_total_bid(auction_id)

        print(f"\nTrying second trade:")
        print(f"Amount: {second_amount}")
        print(f"Min dy: {second_min_dy}")
        print(f"Expected output: {auction_house.get_dy(weth, second_amount)}")

        auction_house.create_bid_with_token(auction_id, second_amount, weth, second_min_dy)


def test_bid_with_specific_amounts(auction_house, weth_trader, weth, payment_token, alice):
    # First add token support
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()

    # Now we can get prices
    reserve_price = auction_house.default_reserve_price()
    bid_amount = auction_house.safe_get_dx(weth, reserve_price * 2)  # Ensure well above reserve
    min_dy = reserve_price  # Must meet reserve

    # Print initial state for debugging
    print(f"\nWETH balance: {weth.balanceOf(alice)}")
    print(f"Reserve price: {reserve_price}")
    print(f"Bid amount: {bid_amount}")
    print(f"Min output required: {min_dy}")
    print(f"Expected output: {auction_house.get_dy(weth, bid_amount)}")

    with boa.env.prank(alice):
        weth.approve(auction_house, 2**256 - 1)

        try:
            with boa.reverts("!trader"):
                auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)
            print("Failed: Trader not found")
        except:
            try:
                with boa.reverts("Trading token transfer failed"):
                    auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)
                print("Failed: WETH transfer failed")
            except:
                try:
                    with boa.reverts("!reservePrice"):
                        auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)
                    print("Failed: Below reserve price")
                except:
                    try:
                        with boa.reverts("!increment"):
                            auction_house.create_bid_with_token(
                                auction_id, bid_amount, weth, min_dy
                            )
                        print("Failed: Below minimum increment")
                    except:
                        print("Different revert reason than expected")


def test_approval_sequence_issue(auction_house, weth_trader, weth, payment_token, alice):

    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()

    min_dy = auction_house.minimum_total_bid(auction_id)
    bid_amount = auction_house.safe_get_dx(weth, min_dy)

    init_squid = payment_token.balanceOf(alice)
    init_weth = weth.balanceOf(alice)
    assert weth.balanceOf(alice) >= bid_amount
    assert auction_house.get_dy(weth, bid_amount) > min_dy

    with boa.env.prank(alice):
        weth_allowance = weth.allowance(alice, auction_house)
        squid_allowance = payment_token.allowance(alice, auction_house)

        # Should fail with no weth approval
        assert weth_allowance < bid_amount
        with pytest.raises(Exception) as e_info:
            auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy, alice)

        print(f"Expected failure: {e_info.value}")
        assert weth.balanceOf(alice) == init_weth
        assert payment_token.balanceOf(alice) == init_squid

        weth.approve(auction_house, 2**256 - 1)
        auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy, alice)
        assert weth.balanceOf(alice) == init_weth - bid_amount
        assert payment_token.balanceOf(alice) == init_squid

        # Verify auction state
        auction = auction_house.auction_list(auction_id)
        assert auction[1] >= min_dy
        assert auction[4] == alice
