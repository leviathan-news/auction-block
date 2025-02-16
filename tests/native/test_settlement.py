import boa


def test_withdraw_zero_pending(auction_house_with_auction, alice, payment_token):
    """Test withdrawing with no pending returns"""
    auction_id = auction_house_with_auction.auction_id()
    boa.env.time_travel(auction_house_with_auction.auction_remaining_time(auction_id) + 1)
    auction_house_with_auction.settle_auction(auction_id)
    with boa.env.prank(alice), boa.reverts("!pending"):
        auction_house_with_auction.withdraw(auction_id)


def test_withdraw_after_outbid(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test withdrawing funds after being outbid"""
    auction_id = auction_house_with_auction.auction_id()
    alice_balance_before = payment_token.balanceOf(alice)

    # Calculate bids
    first_bid = default_reserve_price
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    second_bid = first_bid + (first_bid * min_increment) // precision

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, first_bid)
        auction_house_with_auction.create_bid(auction_id, first_bid)

    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, second_bid)
        auction_house_with_auction.create_bid(auction_id, second_bid)

    # Alice withdraws
    boa.env.time_travel(seconds=4000)
    auction_house_with_auction.settle_auction(auction_id)
    with boa.env.prank(alice):
        auction_house_with_auction.withdraw(auction_id)

    assert payment_token.balanceOf(alice) == alice_balance_before


def test_settle_auction_with_single_bid(
    auction_house_with_auction, alice, deployer, fee_receiver, payment_token, default_reserve_price, precision, default_fee
):
    """Test settling auction with one bid"""
    auction_id = auction_house_with_auction.auction_id()
    bid_amount = default_reserve_price

    # Track balances
    deployer_balance_before = payment_token.balanceOf(deployer)
    fee_receiver_balance_before = payment_token.balanceOf(fee_receiver)

    # Place and settle bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)

    boa.env.time_travel(seconds=4000)

    with boa.env.prank(deployer):
        auction_house_with_auction.settle_auction(auction_id)

    # Fee is 5% to fee_receiver
    fee = bid_amount * default_fee // precision
    owner_amount = bid_amount - fee

    assert payment_token.balanceOf(deployer) - deployer_balance_before == owner_amount
    assert payment_token.balanceOf(fee_receiver) - fee_receiver_balance_before == fee


def test_settle_auction_no_bids(auction_house_with_auction, deployer):
    """Test settling an auction with no bids"""
    auction_id = auction_house_with_auction.auction_id()

    # Get initial state
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    print(f"Initial auction state: {initial_auction}")

    # Fast forward past auction end
    boa.env.time_travel(seconds=4000)

    with boa.env.prank(deployer):
        # auction_house_with_auction.pause()
        auction_house_with_auction.settle_auction(auction_id)
        auction_house_with_auction.create_new_auction()

    # Get final state
    final_auction = auction_house_with_auction.auction_list(auction_id)
    new_auction = auction_house_with_auction.auction_list(auction_id + 1)
    print(f"Final auction state: {final_auction}")
    print(f"New auction state: {new_auction}")
    print(f"New auction ID: {auction_house_with_auction.auction_id()}")

    # Verify auction was settled and new one created
    assert auction_house_with_auction.auction_id() == auction_id + 1
    assert final_auction[5] is True  # settled
    assert new_auction[0] == auction_id + 1  # new auction has correct ID


def test_settle_multiple_bids(
    auction_house_with_auction,
    alice,
    bob,
    deployer,
    proceeds_receiver,
    payment_token,
    default_reserve_price,
    precision
):
    auction_id = auction_house_with_auction.auction_id()
    alice_balance_before = payment_token.balanceOf(alice)

    # Place bids
    first_bid = default_reserve_price
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    second_bid = first_bid + (first_bid * min_increment) // precision

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, first_bid)
        auction_house_with_auction.create_bid(auction_id, first_bid)

    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, second_bid)
        auction_house_with_auction.create_bid(auction_id, second_bid)

    boa.env.time_travel(seconds=4000)

    with boa.env.prank(deployer):
        # auction_house_with_auction.pause()
        auction_house_with_auction.settle_auction(auction_id)

    alice_balance_mid = payment_token.balanceOf(alice)
    assert alice_balance_mid == alice_balance_before - first_bid

    # Alice withdraws with auction_id
    with boa.env.prank(alice):
        auction_house_with_auction.withdraw(auction_id)


def test_settle_auction_not_ended(auction_house_with_auction, deployer):
    """Test cannot settle auction before it ends"""
    auction_id = auction_house_with_auction.auction_id()

    with boa.env.prank(deployer), boa.reverts("!completed"):
        # auction_house_with_auction.pause()
        auction_house_with_auction.settle_auction(auction_id)


def test_auction_extension(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test auction gets extended when bid near end"""
    auction_id = auction_house_with_auction.auction_id()

    # Calculate bid amounts
    first_bid = default_reserve_price
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    second_bid = first_bid + (first_bid * min_increment) // precision

    # Place initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, first_bid)
        auction_house_with_auction.create_bid(auction_id, first_bid)

    # Move to near end of auction
    auction = auction_house_with_auction.auction_list(auction_id)
    time_to_move = auction[3] - auction[2] - 50  # end_time - start_time - 50 seconds
    boa.env.time_travel(seconds=int(time_to_move))

    # Place bid near end
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, second_bid)
        auction_house_with_auction.create_bid(auction_id, second_bid)

    # Check auction was extended
    new_auction = auction_house_with_auction.auction_list(auction_id)
    assert new_auction[3] > auction[3]  # new end_time > old end_time
