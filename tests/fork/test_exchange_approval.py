import boa
import pytest

pytestmark = pytest.mark.fork_only


def test_specific_bid_scenario_proper_fail(auction_house, weth_trader, weth, payment_token, alice):
    bid_amount = 742530561690
    min_dy = 2000000000000000000  # 2 tokens

    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()

    # Record initial balances
    print(f"\nInitial balances:")
    print(f"WETH: {weth.balanceOf(alice)}")
    print(f"SQUID: {payment_token.balanceOf(alice)}")

    with boa.env.prank(alice):
        # ONLY approve WETH trader, not payment token
        weth.approve(auction_house, 2**256 - 1)

        # SHOULD BE POSSIBLE TO BID WITHOUT SQUID APPROVAL
        auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)


def test_various_approval_scenarios(auction_house, weth_trader, weth, payment_token, alice):
    bid_amount = 742530561690
    min_dy = 2000000000000000000

    owner = auction_house.owner()
    with boa.env.prank(owner):
        auction_house.pause()
        auction_house.add_token_support(weth, weth_trader)
        auction_house.unpause()
        auction_id = auction_house.create_new_auction()

    # Print initial state
    print(f"\nInitial WETH balance: {weth.balanceOf(alice)}")
    print(f"Initial trader allowance: {weth.allowance(alice, weth_trader.address)}")

    with boa.env.prank(alice):
        # Try resetting approval to 0 first
        weth.approve(auction_house, 0)
        weth.approve(auction_house, 2**256 - 1)
        payment_token.approve(auction_house, 2**256 - 1)

        print(f"\nAfter approval:")
        print(f"Trader allowance: {weth.allowance(alice, weth_trader.address)}")

        # Try a small test trade first
        small_amount = bid_amount // 10
        small_min_dy = min_dy // 10

        print(f"\nTrying small trade first:")
        print(f"Amount: {small_amount}")
        print(f"Min dy: {small_min_dy}")

        auction_house.create_bid_with_token(auction_id, small_amount, weth, small_min_dy)

        print("\nSmall trade succeeded")

        # Now try the full amount
        print(f"\nTrying full trade:")
        print(f"Amount: {bid_amount}")
        print(f"Min dy: {min_dy}")

        auction_house.create_bid_with_token(auction_id, bid_amount, weth, min_dy)


def test_bid_with_specific_amounts(auction_house, weth_trader, weth, payment_token, alice):
    AUCTION_ID = 4
    BID_AMOUNT = 742530561690
    MIN_DY = 2000000000000000000

    # Print initial state for debugging
    print(f"\nWETH balance: {weth.balanceOf(alice)}")
    print(f"WETH allowance: {weth.allowance(alice, weth_trader)}")
    print(f"Expected output: {weth_trader.get_dy(BID_AMOUNT)}")

    # Try the exchange directly first
    with boa.env.prank(alice):
        weth.approve(auction_house, 2**256 - 1)

        # Try different potential revert conditions
        try:
            with boa.reverts("!trader"):
                weth_trader.exchange(BID_AMOUNT, MIN_DY, alice)
            print("Failed: Trader not found")
        except:
            try:
                with boa.reverts("Trading token transfer failed"):
                    weth_trader.exchange(BID_AMOUNT, MIN_DY, alice)
                print("Failed: WETH transfer failed")
            except:
                try:
                    with boa.reverts("!reservePrice"):
                        auction_house.create_bid_with_token(
                            AUCTION_ID, BID_AMOUNT, weth, MIN_DY, alice
                        )
                    print("Failed: Below reserve price")
                except:
                    try:
                        with boa.reverts("!increment"):
                            auction_house.create_bid_with_token(
                                AUCTION_ID, BID_AMOUNT, weth, MIN_DY, alice
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
