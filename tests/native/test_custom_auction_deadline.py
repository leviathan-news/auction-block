import boa


def test_create_custom_auction_by_deadline(
    auction_house,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    default_duration,
    ipfs_hash,
    auction_params_struct,
    auction_struct,
):
    """Test creating a custom auction with a deadline instead of duration"""
    # Custom parameters different from defaults
    custom_time_buffer = default_time_buffer * 2
    custom_reserve_price = default_reserve_price * 2
    custom_min_bid_increment = default_min_bid_increment + 1

    # Get current start time by creating an auction
    with boa.env.prank(deployer):
        first_auction_id = auction_house.create_new_auction("")

    first_auction = auction_house.auction_list(first_auction_id)
    current_time = first_auction[auction_struct.start_time]

    # Set deadline to 2*default_duration in the future
    custom_deadline = current_time + (default_duration * 2)

    with boa.env.prank(deployer):
        auction_id = auction_house.create_custom_auction_by_deadline(
            custom_time_buffer,
            custom_reserve_price,
            custom_min_bid_increment,
            custom_deadline,
            ipfs_hash,
        )

    # Retrieve the created auction
    auction = auction_house.auction_list(auction_id)

    # Verify auction parameters
    assert auction[auction_struct.auction_id] == auction_id, "Auction ID should match"
    assert auction[auction_struct.amount] == 0, "Initial auction amount should be 0"
    assert auction[auction_struct.start_time] > 0, "Start time should be set"
    assert (
        auction[auction_struct.end_time] == custom_deadline
    ), "End time should match the provided deadline"
    assert (
        auction[auction_struct.bidder] == "0x0000000000000000000000000000000000000000"
    ), "Initial bidder should be empty"
    assert auction[auction_struct.settled] is False, "Auction should not be settled"
    assert auction[auction_struct.ipfs_hash] == ipfs_hash, "IPFS hash should match"

    # Verify auction parameters struct
    auction_params = auction[auction_struct.params]
    assert (
        auction_params[auction_params_struct.time_buffer] == custom_time_buffer
    ), "Time buffer should match custom value"
    assert (
        auction_params[auction_params_struct.reserve_price] == custom_reserve_price
    ), "Reserve price should match custom value"
    assert (
        auction_params[auction_params_struct.min_bid_increment_percentage]
        == custom_min_bid_increment
    ), "Min bid increment percentage should match custom value"
    # Duration should be calculated from deadline - start_time
    duration_diff = abs(
        auction_params[auction_params_struct.duration]
        - (custom_deadline - auction[auction_struct.start_time])
    )
    assert (
        duration_diff <= 5
    ), "Duration should be calculated from deadline (within 5 seconds tolerance)"


def test_create_custom_auction_by_deadline_only_owner(
    auction_house,
    alice,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    auction_struct,
):
    """Test that only the owner can create a custom auction by deadline"""
    # Get current start time by creating an auction
    with boa.env.prank(deployer):
        first_auction_id = auction_house.create_new_auction("")

    first_auction = auction_house.auction_list(first_auction_id)
    current_time = first_auction[auction_struct.start_time]

    # Set deadline to 1 day in the future
    custom_deadline = current_time + 86400

    with boa.env.prank(alice):
        with boa.reverts("!manager"):
            auction_house.create_custom_auction_by_deadline(
                default_time_buffer,
                default_reserve_price,
                default_min_bid_increment,
                custom_deadline,
                "",
            )


def test_create_custom_auction_by_deadline_requires_future_deadline(
    auction_house,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    auction_struct,
):
    """Test that deadline must be in the future"""
    # Get current time first
    with boa.env.prank(deployer):
        auction_id = auction_house.create_new_auction()

    auction = auction_house.auction_list(auction_id)
    current_time = auction[auction_struct.start_time]

    # Set deadline to 1 second in the past
    past_deadline = current_time - 1

    with boa.env.prank(deployer):
        with boa.reverts("!deadline"):
            auction_house.create_custom_auction_by_deadline(
                default_time_buffer,
                default_reserve_price,
                default_min_bid_increment,
                past_deadline,
                "",
            )


def test_auction_manager_can_create_custom_auction_by_deadline(
    auction_house,
    alice,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    auction_struct,
):
    """Test that an authorized auction manager can create a custom auction by deadline"""
    # Authorize alice as an auction manager
    with boa.env.prank(deployer):
        auction_house.set_auction_manager(alice, True)

    # Get current time by creating an auction
    with boa.env.prank(deployer):
        baseline_auction_id = auction_house.create_new_auction("")

    baseline_auction = auction_house.auction_list(baseline_auction_id)
    current_time = baseline_auction[auction_struct.start_time]

    # Set deadline to 1 day in the future
    custom_deadline = current_time + 86400

    curr_auction = auction_house.auction_id()

    # Create auction by deadline as the auction manager
    with boa.env.prank(alice):
        auction_id = auction_house.create_custom_auction_by_deadline(
            default_time_buffer,
            default_reserve_price,
            default_min_bid_increment,
            custom_deadline,
            "",
        )

    assert auction_id == curr_auction + 1, "Auction ID should be incremented"

    # Retrieve the auction and verify end time
    auction = auction_house.auction_list(auction_id)
    assert auction[auction_struct.end_time] == custom_deadline, "End time should match the deadline"


def test_disabled_auction_manager_cannot_create_custom_auction_by_deadline(
    auction_house,
    alice,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    auction_struct,
):
    """Test that a disabled auction manager cannot create a custom auction by deadline"""
    # First, authorize alice as an auction manager
    with boa.env.prank(deployer):
        auction_house.set_auction_manager(alice, True)

    # Get current time by creating an auction
    with boa.env.prank(deployer):
        baseline_auction_id = auction_house.create_new_auction("")

    baseline_auction = auction_house.auction_list(baseline_auction_id)
    current_time = baseline_auction[auction_struct.start_time]

    # Set deadline to 1 day in the future
    custom_deadline = current_time + 86400

    # Create an auction successfully
    with boa.env.prank(alice):
        auction_house.create_custom_auction_by_deadline(
            default_time_buffer,
            default_reserve_price,
            default_min_bid_increment,
            custom_deadline,
            "",
        )

    # Now disable alice as an auction manager
    with boa.env.prank(deployer):
        auction_house.set_auction_manager(alice, False)

    # Attempt to create another auction, which should fail
    with boa.env.prank(alice):
        with boa.reverts("!manager"):
            auction_house.create_custom_auction_by_deadline(
                default_time_buffer,
                default_reserve_price,
                default_min_bid_increment,
                custom_deadline,
                "",
            )


def test_compare_deadline_vs_duration(
    auction_house,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    auction_struct,
):
    """Test that creating an auction by deadline is equivalent to calculated duration"""
    # Get current time by creating an auction
    with boa.env.prank(deployer):
        baseline_auction_id = auction_house.create_new_auction("")

    baseline_auction = auction_house.auction_list(baseline_auction_id)
    current_time = baseline_auction[auction_struct.start_time]

    # Set deadline to 1 day in the future
    custom_deadline = current_time + 86400
    calculated_duration = 86400

    # Create first auction using deadline
    with boa.env.prank(deployer):
        deadline_auction_id = auction_house.create_custom_auction_by_deadline(
            default_time_buffer,
            default_reserve_price,
            default_min_bid_increment,
            custom_deadline,
            "deadline_auction",
        )

    # Create second auction using equivalent duration
    with boa.env.prank(deployer):
        duration_auction_id = auction_house.create_custom_auction(
            default_time_buffer,
            default_reserve_price,
            default_min_bid_increment,
            calculated_duration,
            "duration_auction",
        )

    # Get both auctions
    deadline_auction = auction_house.auction_list(deadline_auction_id)
    duration_auction = auction_house.auction_list(duration_auction_id)

    # The end times should be very close (might be off by a few seconds due to transaction timing)
    # Deadline auction's end time should be fixed at the deadline
    assert (
        deadline_auction[auction_struct.end_time] == custom_deadline
    ), "Deadline auction should end at the specified deadline"

    # Duration auction's end time should be its start time + duration
    expected_duration_end = duration_auction[auction_struct.start_time] + calculated_duration
    assert (
        duration_auction[auction_struct.end_time] == expected_duration_end
    ), "Duration auction should end at start_time + duration"

    # The difference between the two end times should be minimal
    end_time_difference = abs(
        deadline_auction[auction_struct.end_time] - duration_auction[auction_struct.end_time]
    )
    assert end_time_difference <= 5, "End times should be very close (within 5 seconds)"


def test_time_travel_shows_deadline_works(
    auction_house,
    deployer,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    auction_struct,
):
    """Test that using time_travel shows the auction deadline works correctly"""
    # Get current time by creating an auction
    with boa.env.prank(deployer):
        baseline_auction_id = auction_house.create_new_auction("")

    baseline_auction = auction_house.auction_list(baseline_auction_id)
    current_time = baseline_auction[auction_struct.start_time]

    # Set deadline to 1 hour in the future
    custom_deadline = current_time + 3600

    # Create auction with deadline
    with boa.env.prank(deployer):
        deadline_auction_id = auction_house.create_custom_auction_by_deadline(
            default_time_buffer,
            default_reserve_price,
            default_min_bid_increment,
            custom_deadline,
            "deadline_auction",
        )

    # Verify auction is active
    assert auction_house.is_auction_live(deadline_auction_id), "Auction should be live initially"

    # Time travel to just before deadline
    boa.env.time_travel(seconds=3595)  # 5 seconds before deadline

    # Verify auction is still active
    assert auction_house.is_auction_live(
        deadline_auction_id
    ), "Auction should be active before deadline"

    # Time travel past deadline
    boa.env.time_travel(seconds=10)  # 5 seconds past deadline

    # Verify auction is no longer active
    assert not auction_house.is_auction_live(
        deadline_auction_id
    ), "Auction should not be active after deadline"
