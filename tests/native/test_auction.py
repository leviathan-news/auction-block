import boa


def test_initial_state(
    auction_house,
    deployer,
    fee_receiver,
    payment_token,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    default_duration,
    default_fee,
    precision,
):
    """Test the initial state of the auction house after deployment"""
    assert auction_house.owner() == deployer
    assert auction_house.default_time_buffer() == default_time_buffer
    assert auction_house.default_reserve_price() == default_reserve_price
    assert auction_house.default_min_bid_increment_percentage() == default_min_bid_increment
    assert auction_house.default_duration() == default_duration
    assert auction_house.paused() is False
    assert auction_house.fee_receiver() == fee_receiver
    assert auction_house.fee() == default_fee
    assert auction_house.auction_id() == 0
    assert auction_house.payment_token() == payment_token.address


def test_create_auction(auction_house, deployer):
    """Test auction creation and initial auction state"""
    # Need to create an auction first since it's not automatically created
    with boa.env.prank(deployer):
        auction_house.create_new_auction()

    auction_id = auction_house.auction_id()
    auction = auction_house.auction_list(auction_id)

    # Access tuple values by index based on struct definition order
    assert auction[0] == 1  # auction_id
    assert auction[1] == 0  # amount
    assert auction[2] > 0  # start_time
    assert auction[3] == auction[2] + auction_house.default_duration()  # end_time
    assert auction[4] == "0x0000000000000000000000000000000000000000"  # bidder
    assert auction[5] is False  # settled


def test_create_bid(auction_house_with_auction, alice, payment_token, default_reserve_price):
    """Test basic bid creation"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Print initial state
    print(f"Initial auction state: {house.auction_list(auction_id)}")
    print(f"Alice address: {alice}")

    # Test low bid rejection
    low_bid = default_reserve_price // 2
    with boa.env.prank(alice):
        payment_token.approve(house.address, low_bid)
        with boa.reverts("!reservePrice"):
            house.create_bid(auction_id, low_bid)

    # Make valid bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    # Print post-bid state
    auction = house.auction_list(auction_id)
    print(f"Post-bid auction state: {auction}")

    assert auction[4] == alice, f"Expected bidder to be {alice}, got {auction[4]}"
    assert (
        auction[1] == default_reserve_price
    ), f"Expected amount to be {default_reserve_price}, got {auction[1]}"
    assert (
        payment_token.balanceOf(house.address) == default_reserve_price
    ), "Expected house to hold tokens"


def test_outbid(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """Test outbidding functionality"""
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Print initial state
    print(f"Initial auction state: {house.auction_list(auction_id)}")

    # First bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    first_bid_state = house.auction_list(auction_id)
    print(f"After first bid: {first_bid_state}")

    # Calculate minimum next bid
    min_next_bid = default_reserve_price + (
        default_reserve_price * house.default_min_bid_increment_percentage() // precision
    )
    print(f"Minimum next bid required: {min_next_bid}")

    # Try insufficient bid
    insufficient_bid = min_next_bid - 1
    with boa.env.prank(bob):
        payment_token.approve(house.address, insufficient_bid)
        with boa.reverts():
            house.create_bid(auction_id, insufficient_bid)

    # Make successful outbid
    with boa.env.prank(bob):
        payment_token.approve(house.address, min_next_bid)
        house.create_bid(auction_id, min_next_bid)

    # Final state checks
    auction = house.auction_list(auction_id)
    print(f"Final auction state: {auction}")
    print(f"Pending returns for alice: {house.pending_returns(alice)}")

    assert auction[4] == bob, f"Expected bidder to be {bob}, got {auction[4]}"
    assert auction[1] == min_next_bid, f"Expected amount to be {min_next_bid}, got {auction[1]}"
    assert (
        house.pending_returns(alice) == default_reserve_price
    ), f"Expected alice to have her bid of {default_reserve_price} in pending returns"
    # Contract should hold both the current bid and any pending returns
    expected_balance = min_next_bid + house.pending_returns(alice)
    assert (
        payment_token.balanceOf(house.address) == expected_balance
    ), f"Expected house to hold {expected_balance} tokens (current bid + pending returns)"


def test_current_auctions(auction_house_with_auction, deployer):
    """Test that current_auctions only returns currently active auctions"""
    # Initially should show our first auction as active
    active_auctions = auction_house_with_auction.current_auctions()
    assert len(active_auctions) == 1
    assert active_auctions[0] == 1

    # Move forward a bit to separate the auctions in time
    boa.env.time_travel(seconds=1000)

    # Create a second auction (this will start from current time)
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction()

    # Should now show both auctions
    active_auctions = auction_house_with_auction.current_auctions()
    print(f"Active auctions after creating second: {active_auctions}")
    assert len(active_auctions) == 2
    assert active_auctions[0] == 1
    assert active_auctions[1] == 2

    # Fast forward to just before first auction ends
    first_auction = auction_house_with_auction.auction_list(1)
    second_auction = auction_house_with_auction.auction_list(2)
    print(f"First auction: start={first_auction[2]}, end={first_auction[3]}")
    print(f"Second auction: start={second_auction[2]}, end={second_auction[3]}")

    # Travel to 1 second before first auction end
    time_remaining_first_auction = int(first_auction[3]) - (int(first_auction[2]) + 1000) - 1
    print(f"Time remaining until first auction ends: {time_remaining_first_auction}")
    boa.env.time_travel(seconds=time_remaining_first_auction)

    # Should still show both auctions
    active_auctions = auction_house_with_auction.current_auctions()
    print(f"Active auctions near first end: {active_auctions}")
    assert len(active_auctions) == 2

    # Move past first auction end
    boa.env.time_travel(seconds=10)

    # Should only show second auction
    active_auctions = auction_house_with_auction.current_auctions()
    print(f"Active auctions after first ends: {active_auctions}")
    assert len(active_auctions) == 1
    assert active_auctions[0] == 2

    # Settle the first auction
    with boa.env.prank(deployer):
        auction_house_with_auction.settle_auction(1)

    # Should still only show second auction
    active_auctions = auction_house_with_auction.current_auctions()
    assert len(active_auctions) == 1
    assert active_auctions[0] == 2

    # Fast forward past all auctions
    boa.env.time_travel(seconds=4000)  # Well past second auction

    # Should show no active auctions
    active_auctions = auction_house_with_auction.current_auctions()
    assert len(active_auctions) == 0
