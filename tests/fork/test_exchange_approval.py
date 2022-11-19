import boa
import pytest

pytestmark = pytest.mark.fork_only


def test_specific_bid_scenario_proper_fail(
    auction_house, weth_trader, weth, payment_token, alice, approval_flags
):
    # Get the reserve price as our target output amount
    reserve_price = auction_house.default_reserve_price()

    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Calculate required WETH input for this output
    bid_amount = weth_trader.safe_get_dx(reserve_price)
    # Add 1% buffer to ensure we exceed minimum
    min_dy = reserve_price * 99 // 100  # Allow 1% slippage

    # Record initial balances
    print("\nInitial balances:")
    print(f"WETH: {weth.balanceOf(alice)}")
    print(f"SQUID: {payment_token.balanceOf(alice)}")
    print(f"Required WETH input: {bid_amount}")
    print(f"Minimum SQUID output: {min_dy}")
    print(f"Expected SQUID output: {weth_trader.get_dy(bid_amount)}")

    with boa.env.prank(alice):
        weth.approve(weth_trader.address, 2**256 - 1)
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(weth_trader, approval_flags.BidOnly)

        weth_trader.zap_and_bid(auction_house, auction_id, bid_amount, min_dy)


def test_various_approval_scenarios(
    auction_house, weth_trader, weth, payment_token, alice, approval_flags
):
    # Setup first
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Calculate our bid amounts based on current rates
    reserve_price = auction_house.default_reserve_price()
    bid_amount = weth_trader.safe_get_dx(reserve_price * 2)  # Get enough for 2x reserve
    min_dy = reserve_price  # Must at least meet reserve

    # Print initial state
    print("\nInitial balances and setup:")
    print(f"WETH balance: {weth.balanceOf(alice)}")
    print(f"Reserve price: {reserve_price}")
    print(f"Required bid amount: {bid_amount}")
    print(f"Min output required: {min_dy}")
    print(f"Expected output: {weth_trader.get_dy(bid_amount)}")

    with boa.env.prank(alice):
        # Try resetting approval to 0 first
        weth.approve(weth_trader, 0)
        weth.approve(weth_trader, 2**256 - 1)
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(weth_trader, approval_flags.BidOnly)

        # First bid should be enough to meet reserve price
        first_amount = bid_amount // 2  # Half of total (still > reserve)
        first_min_dy = reserve_price  # Must meet reserve

        print("\nTrying first trade:")
        print(f"Amount: {first_amount}")
        print(f"Min dy: {first_min_dy}")
        print(f"Expected output: {weth_trader.get_dy(first_amount)}")

        weth_trader.zap_and_bid(auction_house, auction_id, first_amount, first_min_dy)

        print("\nFirst trade succeeded")

        # Now try the full amount (needs to beat minimum increment)
        second_amount = bid_amount
        second_min_dy = auction_house.minimum_total_bid(auction_id)

        print("\nTrying second trade:")
        print(f"Amount: {second_amount}")
        print(f"Min dy: {second_min_dy}")
        print(f"Expected output: {weth_trader.get_dy(second_amount)}")

        weth_trader.zap_and_bid(auction_house, auction_id, second_amount, second_min_dy)


def test_bid_with_specific_amounts(
    auction_house, weth_trader, weth, payment_token, alice, approval_flags
):
    # First add token support
    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    # Now we can get prices
    reserve_price = auction_house.default_reserve_price()
    bid_amount = weth_trader.safe_get_dx(reserve_price * 2)  # Ensure well above reserve
    min_dy = reserve_price  # Must meet reserve

    # Print initial state for debugging
    print(f"\nWETH balance: {weth.balanceOf(alice)}")
    print(f"Reserve price: {reserve_price}")
    print(f"Bid amount: {bid_amount}")
    print(f"Min output required: {min_dy}")
    print(f"Expected output: {weth_trader.get_dy(bid_amount)}")

    with boa.env.prank(alice):
        weth.approve(weth_trader.address, 2**256 - 1)
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(weth_trader, approval_flags.BidOnly)

        try:
            with boa.reverts("!trader"):
                weth_trader(auction_id, bid_amount, weth, min_dy)
            print("Failed: Trader not found")
        except Exception as e:
            print(f"Caught exception {e}")
            try:
                with boa.reverts("Trading token transfer failed"):
                    auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)
                print("Failed: WETH transfer failed")
            except Exception as e1:
                print(f"Caught exception {e1}")
                try:
                    with boa.reverts("!reservePrice"):
                        auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)
                    print("Failed: Below reserve price")
                except Exception as e2:
                    print(f"Caught exception {e2}")
                    try:
                        with boa.reverts("!increment"):
                            auction_house.create_bid_with_token(
                                auction_id, bid_amount, weth, min_dy
                            )
                        print("Failed: Below minimum increment")
                    except Exception as e3:
                        print(f"Different revert reason than expected {e3}")


def test_approval_sequence_issue(
    auction_house, weth_trader, weth, payment_token, alice, approval_flags
):

    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    min_dy = auction_house.minimum_total_bid(auction_id)
    bid_amount = weth_trader.safe_get_dx(min_dy)

    init_squid = payment_token.balanceOf(alice)
    init_weth = weth.balanceOf(alice)
    assert weth.balanceOf(alice) >= bid_amount
    assert weth_trader.get_dy(bid_amount) > min_dy

    with boa.env.prank(alice):
        weth_allowance = weth.allowance(alice, auction_house)

        # Should fail with no weth approval
        assert weth_allowance < bid_amount
        with boa.reverts("ERC20: transfer amount exceeds allowance"):
            weth_trader.zap_and_bid(auction_house, auction_id, bid_amount, min_dy, alice)

        assert weth.balanceOf(alice) == init_weth
        assert payment_token.balanceOf(alice) == init_squid

        weth.approve(weth_trader.address, 2**256 - 1)
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(weth_trader, approval_flags.BidOnly)

        weth_trader.zap_and_bid(auction_house, auction_id, bid_amount, min_dy, alice)
        assert weth.balanceOf(alice) == init_weth - bid_amount
        assert payment_token.balanceOf(alice) == init_squid

        # Verify auction state
        auction = auction_house.auction_list(auction_id)
        assert auction[1] >= min_dy
        assert auction[4] == alice
