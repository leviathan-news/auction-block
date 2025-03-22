import boa


def test_create_custom_auction(
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
    """Test creating a custom auction with non-default parameters"""
    # Custom parameters different from defaults
    custom_time_buffer = default_time_buffer * 2
    custom_reserve_price = default_reserve_price * 2
    custom_min_bid_increment = default_min_bid_increment + 1
    custom_duration = default_duration * 2

    with boa.env.prank(deployer):
        auction_id = auction_house.create_custom_auction(
            custom_time_buffer,
            custom_reserve_price,
            custom_min_bid_increment,
            custom_duration,
            ipfs_hash,
        )

    # Retrieve the created auction
    auction = auction_house.auction_list(auction_id)

    # Verify auction parameters
    assert auction[auction_struct.auction_id] == auction_id, "Auction ID should match"
    assert auction[auction_struct.amount] == 0, "Initial auction amount should be 0"
    assert auction[auction_struct.start_time] > 0, "Start time should be set"
    assert (
        auction[auction_struct.end_time] == auction[auction_struct.start_time] + custom_duration
    ), "End time should be calculated from custom duration"
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
    assert (
        auction_params[auction_params_struct.duration] == custom_duration
    ), "Duration should match custom value"


def test_create_custom_auction_only_owner(
    auction_house,
    alice,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    default_duration,
):
    """Test that only the owner can create a custom auction"""
    with boa.env.prank(alice):
        with boa.reverts("!manager"):
            auction_house.create_custom_auction(
                default_time_buffer,
                default_reserve_price,
                default_min_bid_increment,
                default_duration,
                "",
            )


def test_can_authorize_auction_manager(auction_house, alice, deployer):
    curr_auction = auction_house.auction_id()
    with boa.env.prank(deployer):
        auction_house.set_auction_manager(alice, True)

    with boa.env.prank(alice):
        auction_house.create_new_auction()

    assert curr_auction + 1 == auction_house.auction_id()


def test_can_authorize_auction_manager_custom_auction(auction_house, alice, deployer):
    curr_auction = auction_house.auction_id()
    with boa.env.prank(deployer):
        auction_house.set_auction_manager(alice, True)

    with boa.env.prank(alice):
        auction_house.create_custom_auction(
            auction_house.default_time_buffer(),
            auction_house.default_reserve_price(),
            auction_house.default_min_bid_increment_percentage(),
            auction_house.default_duration(),
        )

    assert curr_auction + 1 == auction_house.auction_id()


def test_can_disable_auction_manager(auction_house, alice, deployer):
    curr_auction = auction_house.auction_id()
    with boa.env.prank(deployer):
        auction_house.set_auction_manager(alice, True)

    with boa.env.prank(alice):
        auction_house.create_new_auction()

    assert curr_auction + 1 == auction_house.auction_id()

    with boa.env.prank(deployer):
        auction_house.set_auction_manager(alice, False)

    with boa.env.prank(alice):
        with boa.reverts("!manager"):
            auction_house.create_new_auction()

    assert curr_auction + 1 == auction_house.auction_id()


def test_rando_cannot_designate_auction_manager(auction_house, alice, bob):

    curr_auction = auction_house.auction_id()
    with boa.env.prank(alice):
        with boa.reverts("!owner"):
            auction_house.set_auction_manager(alice, True)
        with boa.reverts("!owner"):
            auction_house.set_auction_manager(bob, True)

    with boa.env.prank(alice):
        with boa.reverts("!manager"):
            auction_house.create_new_auction()

    with boa.env.prank(bob):
        with boa.reverts("!manager"):
            auction_house.create_new_auction()

    assert curr_auction == auction_house.auction_id()


def test_instabuy_auction(
    auction_house,
    deployer,
    alice,
    bob,
    payment_token,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    default_duration,
    auction_params_struct,
    auction_struct,
    zero_address,
):
    """Test auction with instabuy price - verifies instabuy functionality"""
    # Set instabuy price to double the reserve price
    instabuy_price = default_reserve_price * 2

    # Create auction with instabuy price
    with boa.env.prank(deployer):
        auction_id = auction_house.create_custom_auction(
            default_time_buffer,
            default_reserve_price,
            default_min_bid_increment,
            default_duration,
            "",  # ipfs_hash
            instabuy_price,  # instabuy_price
            zero_address,  # beneficiary (default to owner)
        )

    # Verify instabuy price is set correctly
    auction = auction_house.auction_list(auction_id)
    auction_params = auction[auction_struct.params]
    assert (
        auction_params[auction_params_struct.instabuy_price] == instabuy_price
    ), "Instabuy price should be set correctly"

    # Test bid below instabuy price
    with boa.env.prank(alice):
        payment_token.approve(auction_house.address, default_reserve_price)
        auction_house.create_bid(auction_id, default_reserve_price)

    # Verify auction is still active
    auction = auction_house.auction_list(auction_id)
    assert (
        auction[auction_struct.settled] is False
    ), "Auction should still be active after bid below instabuy"
    assert auction[auction_struct.bidder] == alice, "Alice should be current bidder"

    # Test bid above instabuy price (bob outbids with instabuy)
    with boa.env.prank(bob):
        payment_token.approve(auction_house.address, instabuy_price)
        auction_house.create_bid(auction_id, instabuy_price)

    # Verify auction is now settled
    auction = auction_house.auction_list(auction_id)
    assert auction[auction_struct.settled] is True, "Auction should be settled after instabuy"
    assert auction[auction_struct.bidder] == bob, "Bob should be the winner"
    assert (
        auction[auction_struct.amount] == instabuy_price
    ), "Winning amount should be instabuy price"

    # Verify alice's bid was refunded
    alice_pending = auction_house.auction_pending_returns(auction_id, alice)
    assert alice_pending == default_reserve_price, "Alice's bid should be added to pending returns"


def test_instabuy_with_beneficiary(
    auction_house,
    deployer,
    alice,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
    auction_params_struct,
):
    """Test auction with both instabuy and custom beneficiary"""
    # Create a custom beneficiary address
    beneficiary = boa.env.generate_address()

    # Set fee to 10%
    test_fee = 10
    with boa.env.prank(deployer):
        auction_house.set_fee_percent(test_fee)

    # Set instabuy price to double the reserve price
    instabuy_price = default_reserve_price * 2

    # Create auction with both instabuy and beneficiary
    with boa.env.prank(deployer):
        auction_id = auction_house.create_custom_auction(
            auction_house.default_time_buffer(),
            default_reserve_price,
            auction_house.default_min_bid_increment_percentage(),
            auction_house.default_duration(),
            "",  # ipfs_hash
            instabuy_price,  # instabuy_price
            beneficiary,  # custom beneficiary
        )

    # Verify both instabuy price and beneficiary are set correctly
    auction = auction_house.auction_list(auction_id)
    auction_params = auction[auction_struct.params]
    assert (
        auction_params[auction_params_struct.instabuy_price] == instabuy_price
    ), "Instabuy price should be set correctly"
    assert (
        auction_params[auction_params_struct.beneficiary] == beneficiary
    ), "Beneficiary should be set correctly"

    # Record balances before instabuy
    fee_receiver = auction_house.fee_receiver()
    fee_receiver_balance_before = payment_token.balanceOf(fee_receiver)
    beneficiary_balance_before = payment_token.balanceOf(beneficiary)

    # Alice performs instabuy
    with boa.env.prank(alice):
        payment_token.approve(auction_house.address, instabuy_price)
        auction_house.create_bid(auction_id, instabuy_price)

    # Verify auction is now settled
    auction = auction_house.auction_list(auction_id)
    assert auction[auction_struct.settled] is True, "Auction should be settled after instabuy"
    assert auction[auction_struct.bidder] == alice, "Alice should be the winner"
    assert (
        auction[auction_struct.amount] == instabuy_price
    ), "Winning amount should be instabuy price"

    # Verify fee distribution
    expected_fee = instabuy_price * test_fee // precision
    expected_remaining = instabuy_price - expected_fee

    fee_receiver_balance_after = payment_token.balanceOf(fee_receiver)
    beneficiary_balance_after = payment_token.balanceOf(beneficiary)

    assert (
        fee_receiver_balance_after - fee_receiver_balance_before == expected_fee
    ), "Fee receiver should receive correct fee amount"
    assert (
        beneficiary_balance_after - beneficiary_balance_before == expected_remaining
    ), "Beneficiary should receive remaining amount"
