import boa
import pytest

pytestmark = pytest.mark.fork_only


def test_rebid_with_alternative_token(
    auction_house, weth_trader, weth, payment_token, alice, bob, directory
):
    """
    Test that rebidding with alternative tokens only requires trading the difference needed
    when a user is outbid and wants to bid again.
    """
    owner = auction_house.owner()

    # Setup
    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()
        directory.add_token_support(weth, weth_trader)

    # 1. Alice's initial bid
    min_bid = auction_house.minimum_total_bid(auction_id)
    weth_amount = directory.safe_get_dx(weth, min_bid)

    with boa.env.prank(alice):
        alice_init_weth = weth.balanceOf(alice)
        weth.approve(directory, 2**256 - 1)
        directory.create_bid_with_token(auction_house, auction_id, weth_amount, weth, min_bid)
        alice_first_spend = alice_init_weth - weth.balanceOf(alice)

    print("\nStep 1: Alice's first bid:")
    print(f"WETH spent: {alice_first_spend}")
    print(f"Min bid required: {min_bid}")

    # 2. Bob outbids Alice
    min_bid_bob = auction_house.minimum_total_bid(auction_id)
    weth_amount_bob = directory.safe_get_dx(weth, min_bid_bob)

    with boa.env.prank(bob):
        weth.approve(directory, 2**256 - 1)
        directory.create_bid_with_token(
            auction_house, auction_id, weth_amount_bob, weth, min_bid_bob
        )

    print("\nStep 2: Bob's outbid:")
    print(f"Min bid required: {min_bid_bob}")
    print(f"Alice's pending returns: {auction_house.pending_returns(alice)}")

    # 3. Alice rebids
    min_bid_alice_rebid = auction_house.minimum_total_bid(auction_id)
    min_additional_bid = auction_house.minimum_additional_bid_for_user(auction_id, alice)
    weth_amount_rebid = directory.safe_get_dx(weth, min_additional_bid)

    with boa.env.prank(alice):
        weth_balance_before_rebid = weth.balanceOf(alice)
        directory.create_bid_with_token(
            auction_house, auction_id, weth_amount_rebid, weth, min_bid_alice_rebid
        )
        alice_rebid_spend = weth_balance_before_rebid - weth.balanceOf(alice)

    print("\nStep 3: Alice's rebid:")
    print(f"WETH spent on rebid: {alice_rebid_spend}")
    print(f"Original WETH spent: {alice_first_spend}")
    print(f"Min bid required: {min_bid_alice_rebid}")
    print(f"Min additional bid: {min_additional_bid}")

    # Key assertion - Alice's rebid should only require trading the increment needed
    # not the full amount since she has pending returns
    assert alice_rebid_spend < alice_first_spend, (
        f"Alice's rebid WETH spend ({alice_rebid_spend}) should be less than "
        f"her first spend ({alice_first_spend}) when rebidding with pending returns"
    )

    # Additional sanity checks
    auction = auction_house.auction_list(auction_id)
    assert auction[4] == alice  # Alice should be winning bidder
    assert auction[1] >= min_bid_alice_rebid  # Bid amount should meet minimum
