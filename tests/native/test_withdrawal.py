import boa
import pytest

def test_withdraw_stale(
    auction_house_with_auction,
    deployer,
    alice,
    bob,
    payment_token,
    fee_receiver,
    default_reserve_price,
    default_fee,
    precision,
):
    """Test admin withdrawal of stale pending returns"""
    auction_id = auction_house_with_auction.auction_id()

    # Create pending returns
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)

    # Bob outbids
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    next_bid = default_reserve_price + (default_reserve_price * min_increment) // precision
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, next_bid)
        auction_house_with_auction.create_bid(auction_id, next_bid)

    # Settlement
    expiry_time = auction_house_with_auction.auction_remaining_time(auction_id) + 1
    boa.env.time_travel(seconds=expiry_time)
    with boa.env.prank(deployer):
        auction_house_with_auction.settle_auction(auction_id)

    # Record balances after settlement but before stale withdrawal
    balance_before_withdrawal = payment_token.balanceOf(alice)
    fee_receiver_before_stale = payment_token.balanceOf(fee_receiver)
    pending_amount = auction_house_with_auction.auction_pending_returns(auction_id, alice)
    assert pending_amount > 0

    print("\nBefore withdraw_stale:")
    print(f"Fee receiver balance: {fee_receiver_before_stale}")
    print(f"Pending amount: {pending_amount}")
    print(f"Contract fee: {auction_house_with_auction.fee_percent()}")
    print(f"Default fee from params: {default_fee}")
    print(f"Precision: {precision}")

    # Admin stale withdrawal
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice])

    # After withdrawal checks
    assert auction_house_with_auction.auction_pending_returns(auction_id, alice) == 0
    balance_after_withdrawal = payment_token.balanceOf(alice)

    # Calculate expected fee using contract's fee parameter and precision
    expected_stale_fee = pending_amount * auction_house_with_auction.fee_percent() // precision
    expected_return = pending_amount - expected_stale_fee
    fee_from_stale = payment_token.balanceOf(fee_receiver) - fee_receiver_before_stale
    amount_to_alice = balance_after_withdrawal - balance_before_withdrawal

    print("\nAfter withdraw_stale:")
    print(f"Fee from stale withdrawal: {fee_from_stale}")
    print(f"Expected stale fee: {expected_stale_fee}")
    print(f"Amount returned to alice: {amount_to_alice}")
    print(f"Expected return to alice: {expected_return}")

    # Verify the amounts
    assert (
        fee_from_stale == expected_stale_fee
    ), f"Fee amount incorrect: got {fee_from_stale}, expected {expected_stale_fee}"
    assert amount_to_alice == expected_return, "Return amount to alice incorrect"


def test_withdraw_stale_multiple_users(
    auction_house_with_auction,
    alice,
    bob,
    charlie,
    deployer,
    payment_token,
    fee_receiver,
    precision,
):
    """Test admin withdrawal for multiple users with various states"""
    auction_id = auction_house_with_auction.auction_id()

    # Track initial balances
    balances_before = {
        alice: payment_token.balanceOf(alice),
        bob: payment_token.balanceOf(bob),
        charlie: payment_token.balanceOf(charlie),
        fee_receiver: payment_token.balanceOf(fee_receiver),
        deployer: payment_token.balanceOf(deployer),
    }

    # Bob bids first
    first_bid = auction_house_with_auction.default_reserve_price()
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, first_bid)
        auction_house_with_auction.create_bid(auction_id, first_bid)

    # Charlie wins with higher bid
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()
    second_bid = first_bid + (first_bid * min_increment // precision)
    with boa.env.prank(charlie):
        payment_token.approve(auction_house_with_auction.address, second_bid)
        auction_house_with_auction.create_bid(auction_id, second_bid)

    # Settlement
    expiry_time = auction_house_with_auction.auction_remaining_time(auction_id) + 1
    boa.env.time_travel(seconds=expiry_time)
    with boa.env.prank(deployer):
        auction_house_with_auction.settle_auction(auction_id)

    # Admin withdraws stale returns for all users
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice, bob, charlie])

    # Calculate expected amounts
    stale_fee = (
        first_bid * auction_house_with_auction.fee_percent() // precision
    )  # 5% fee on Bob's stale return
    bob_return = first_bid - stale_fee
    fee_from_bid = second_bid * auction_house_with_auction.fee_percent() // precision
    owner_share = second_bid - fee_from_bid

    # Verify final balances
    assert payment_token.balanceOf(alice) == balances_before[alice]  # Unchanged
    assert payment_token.balanceOf(bob) == balances_before[bob] - first_bid + bob_return
    assert payment_token.balanceOf(charlie) == balances_before[charlie] - second_bid
    assert (
        payment_token.balanceOf(fee_receiver)
        == balances_before[fee_receiver] + stale_fee + fee_from_bid
    )
    assert payment_token.balanceOf(deployer) == balances_before[deployer] + owner_share


def test_create_bid_with_pending_returns(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
):
    """Test using pending returns for a new bid"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Calculate bid amounts
    initial_bid = default_reserve_price
    bob_bid = initial_bid + (initial_bid * min_increment) // precision
    final_bid = bob_bid + (bob_bid * min_increment) // precision
    additional_amount = final_bid - initial_bid

    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, initial_bid)
        auction_house_with_auction.create_bid(auction_id, initial_bid)

    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_bid)
        auction_house_with_auction.create_bid(auction_id, bob_bid)

    # Verify Alice's pending returns
    assert auction_house_with_auction.pending_returns(alice) == initial_bid

    # Alice uses pending returns plus additional tokens for new higher bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, additional_amount)
        auction_house_with_auction.create_bid(auction_id, final_bid)

    auction = auction_house_with_auction.auction_list(auction_id)
    assert auction[auction_struct.bidder] == alice  # bidder
    assert auction[auction_struct.amount] == final_bid  # amount
    assert auction_house_with_auction.pending_returns(alice) == 0  # Used up pending returns


def test_create_bid_insufficient_pending_returns(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
):
    """Test bid fails when pending returns aren't enough"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.default_min_bid_increment_percentage()

    # Calculate bid amounts
    initial_bid = default_reserve_price
    bob_bid = initial_bid + (initial_bid * min_increment) // precision
    attempted_bid = bob_bid * 2  # Try to bid way higher

    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, initial_bid)
        auction_house_with_auction.create_bid(auction_id, initial_bid)

    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_bid)
        auction_house_with_auction.create_bid(auction_id, bob_bid)

    # Alice tries to bid too high with insufficient returns and insufficient approval
    with boa.env.prank(alice):
        # Only approve a small amount, not enough with pending returns
        payment_token.approve(auction_house_with_auction.address, initial_bid)
        with boa.reverts():  # Expected to fail on token transfer
            auction_house_with_auction.create_bid(auction_id, attempted_bid)

    # State should be unchanged
    auction = auction_house_with_auction.auction_list(auction_id)
    assert auction[auction_struct.bidder] == bob  # still bob's bid
    assert auction[auction_struct.amount] == bob_bid  # amount unchanged
    assert auction_house_with_auction.pending_returns(alice) == initial_bid


def test_prevent_bid_cycling_attack(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
):
    """
    Test that the contract prevents bid cycling attacks by not allowing
    withdrawals during active auctions.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)

    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = initial_bid + (initial_bid * min_increment // precision)

    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)

    # Step 2: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)

    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == initial_bid, "Alice should have pending returns"

    # Step 3: Attempt to withdraw during active auction - should succeed
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice reclaims"

    # Verify auction state remains unchanged
    auction = house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == bob, "Bob should still be winning bidder"
    assert auction[auction_struct.amount] == second_bid, "Bid amount should be unchanged"
    assert house.pending_returns(alice) == 0, "Pending returns should be cleared"

    # Now end the auction and verify withdrawal works
    expiry_time = house.auction_remaining_time(auction_id) + 1
    boa.env.time_travel(seconds=expiry_time)

    with boa.env.prank(alice):
        house.settle_auction(auction_id)
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
        assert payment_token.balanceOf(alice) == initial_balance_alice, "No bonus amount"

    # Verify withdrawal succeeded after auction ended
    assert house.pending_returns(alice) == 0, "Pending returns should still be cleared"


def test_prevent_bid_cycling_attack_with_early_withdrawal(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
):
    """
    Test that the contract prevents bid cycling attacks even when
    allowing early withdrawals. A bid cycling attack would involve:
    1. Alice bids
    2. Bob outbids Alice
    3. Alice withdraws her funds
    4. Alice tries to use those same funds to outbid Bob by a small amount
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    initial_balance_bob = payment_token.balanceOf(bob)

    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment_pct = house.default_min_bid_increment_percentage()

    # Bob's bid will be initial_bid + increment
    bob_bid = initial_bid + (initial_bid * min_increment_pct // precision)

    # If Alice withdraws and tries to cycle, her new bid would need to be:
    alice_second_bid = bob_bid + (bob_bid * min_increment_pct // precision)

    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)

    # Step 2: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)

    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == initial_bid, "Alice should have pending returns"

    # Step 3: Alice withdraws during active auction
    with boa.env.prank(alice):
        house.withdraw(auction_id)

    # Verify Alice got her funds back
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice should have received her initial balance back"
    assert house.pending_returns(alice) == 0, "Alice's pending returns should be cleared"

    # Step 4: Alice attempts to use the same funds for a bid cycling attack
    # Alice would need exactly her initial bid plus the required increment for Bob's bid
    # This tests that Alice can't just recycle the same amount of funds
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)  # Only approve her original amount

        # This should fail because Alice needs more funds than her original bid
        with boa.reverts():  # Expect revert due to insufficient approval
            house.create_bid(auction_id, alice_second_bid)

    # Verify auction state remains unchanged
    auction = house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == bob, "Bob should still be winning bidder"
    assert auction[auction_struct.amount] == bob_bid, "Bid amount should be unchanged"

    # Additional funds test - verify Alice can bid if she has additional funds
    alice_additional_funds = alice_second_bid - initial_bid

    # Mint Alice additional tokens to properly outbid Bob
    payment_token._mint_for_testing(alice, alice_additional_funds)

    # Now Alice can successfully place a higher bid with additional funds
    with boa.env.prank(alice):
        payment_token.approve(house.address, alice_second_bid)
        house.create_bid(auction_id, alice_second_bid)

    # Verify Alice is now the highest bidder
    auction = house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == alice, "Alice should now be winning bidder"
    assert auction[auction_struct.amount] == alice_second_bid, "Bid amount should be updated"

    # Verify Bob now has pending returns
    assert house.pending_returns(bob) == bob_bid, "Bob should have pending returns"

def test_allow_withdrawal_during_active_auction(
    auction_house_with_auction, alice, bob, payment_token, default_reserve_price, precision
):
    """
    Security test to ensure users CAN withdraw pending returns while an auction
    is still active. Test should fail if functionality is blocked.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)

    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = initial_bid + (initial_bid * min_increment // precision)

    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)

    # Step 2: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)

    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == initial_bid, "Setup failed: Alice should have pending returns"

    # Attempt to withdraw during active auction - this should succeed
    with boa.env.prank(alice):
        house.withdraw(auction_id)

    # Double-check Alice could withdraw by verifying her balance has changed
    assert (
        payment_token.balanceOf(alice) == initial_balance_alice 
    ), "User was able to withdraw during active auction!"

    # Now properly end the auction
    expiry_time = house.auction_remaining_time(auction_id) + 1
    boa.env.time_travel(seconds=expiry_time)  # Past auction end time

    # Now withdrawal should succeed
    with boa.env.prank(alice):
        house.settle_auction(auction_id)
        with boa.reverts("!pending"):
            house.withdraw(auction_id)

    # Verify withdrawal worked after auction ended
    assert (
        payment_token.balanceOf(alice) == initial_balance_alice
    ), "Withdrawal succeeded"


def test_prevent_multi_auction_withdrawal_manipulation(
    auction_house_with_auction,
    alice,
    bob,
    deployer,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test to prevent users from using pending returns from one auction
    to bid on another auction while both are active.
    """
    house = auction_house_with_auction
    auction1_id = house.auction_id()

    # Create a second auction
    with boa.env.prank(deployer):
        auction2_id = house.create_new_auction()

    # Initial bid on first auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction1_id, default_reserve_price)

    # Bob outbids on first auction
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction1_id, second_bid)

    # Attempt to use pending returns from auction1 to bid on auction2
    with boa.env.prank(alice):
        with boa.reverts():
            house.create_bid(auction2_id, default_reserve_price)


def test_prevent_withdrawal_amount_manipulation(
    auction_house_with_auction, alice, bob, charlie, payment_token, default_reserve_price, precision
):
    """
    Test to prevent manipulation of withdrawal amounts through
    complex bidding patterns.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    initial_balance_alice = payment_token.balanceOf(alice)

    # Create a series of bids and outbids
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 2)
        house.create_bid(auction_id, default_reserve_price)

    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)

    charlie_bid = bob_bid + (bob_bid * min_increment // precision)
    with boa.env.prank(charlie):
        payment_token.approve(house.address, charlie_bid)
        house.create_bid(auction_id, charlie_bid)

    # End auction
    expiry_time = house.auction_remaining_time(auction_id) + 1
    boa.env.time_travel(seconds=expiry_time)

    # Verify withdrawal amount matches original bid exactly
    with boa.env.prank(alice):
        house.settle_auction(auction_id)
        house.withdraw(auction_id)

    assert (
        payment_token.balanceOf(alice) == initial_balance_alice
    ), "Withdrawal amount does not match expected value"


def test_prevent_cross_auction_balance_manipulation(
    auction_house_with_auction,
    alice,
    bob,
    deployer,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test to prevent users from manipulating their balances across multiple
    auctions to get more funds out than they put in.
    """
    house = auction_house_with_auction
    auction1_id = house.auction_id()

    # Create a second auction
    with boa.env.prank(deployer):
        auction2_id = house.create_new_auction()

    initial_balance_alice = payment_token.balanceOf(alice)

    # Bid on first auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction1_id, default_reserve_price)

    # Get outbid on first auction
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction1_id, bob_bid)

    # Try to bid on second auction
    with boa.env.prank(alice):
        with boa.reverts():
            house.create_bid(auction2_id, default_reserve_price)

    # End first auction and withdraw
    expiry_time = house.auction_remaining_time(auction2_id) + 1
    boa.env.time_travel(seconds=expiry_time)
    with boa.env.prank(alice):
        house.settle_auction(auction1_id)
        house.withdraw(auction1_id)

    # Verify total withdrawable never exceeds total deposited
    assert (
        payment_token.balanceOf(alice) <= initial_balance_alice
    ), "User was able to withdraw more than they deposited"


def test_boundary_condition_end_time(auction_house_dual_bid):
    house = auction_house_dual_bid
    auction_id = house.auction_id()

    assert house.is_auction_live(auction_id) is True
    boa.env.time_travel(house.auction_remaining_time(auction_id))
    assert house.is_auction_live(auction_id) is True
    boa.env.time_travel(1)
    assert house.is_auction_live(auction_id) is False

def test_can_withdraw_before_auction_ends(auction_house_dual_bid, alice, payment_token):
    house = auction_house_dual_bid
    auction_id = house.auction_id()
    init_alice = payment_token.balanceOf(alice)

    boa.env.time_travel(house.auction_remaining_time(auction_id))
    pending = house.pending_returns(alice)

    assert house.is_auction_live(auction_id) is True
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    assert init_alice + pending == payment_token.balanceOf(alice)


def test_cannot_withdraw_twice(
    auction_house_dual_bid, alice, bob, payment_token, deployer, approval_flags
):
    house = auction_house_dual_bid
    auction_id = house.auction_id()

    boa.env.time_travel(house.auction_remaining_time(auction_id) + 1)
    house.settle_auction(auction_id)

    init_alice = payment_token.balanceOf(alice)
    init_house = payment_token.balanceOf(house)
    with boa.env.prank(alice):
        house.withdraw(auction_id)
        assert payment_token.balanceOf(alice) == init_alice + house.default_reserve_price()

        with boa.reverts("!pending"):
            house.withdraw(auction_id)

        # Deputize Bob!
        house.set_approved_caller(bob, approval_flags.WithdrawOnly)

    # Deputy Bob also fails
    with boa.env.prank(bob):
        with boa.reverts("!pending"):
            house.withdraw(auction_id, alice)

    assert payment_token.balanceOf(alice) == init_alice + house.default_reserve_price()
    assert payment_token.balanceOf(house) == init_house - house.default_reserve_price()

def test_auction_winner_cannot_withdraw(
    auction_house_dual_bid, alice, bob, payment_token, deployer, approval_flags, auction_struct
):
    house = auction_house_dual_bid

    auction_id = house.auction_id()
    auction_data = house.auction_list(auction_id)

    assert auction_data[auction_struct.bidder] == bob  # Bob is winning!
    boa.env.time_travel(house.auction_remaining_time(auction_id) + 1)

    with boa.env.prank(bob):
        house.settle_auction(auction_id)
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
        house.set_approved_caller(alice, approval_flags.WithdrawOnly)

    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id, bob)


def test_balances_correct_on_dual_auction_split_wins_withdraw_regular(
    auction_house_dual_bid,
    alice,
    bob,
    payment_token,
    deployer,
    approval_flags,
    fee_receiver,
    user_mint_amount,
    precision,
    auction_struct,
):

    # Audit initial state
    house = auction_house_dual_bid
    first_auction = house.auction_id()
    first_auction_bid_alice = house.auction_pending_returns(first_auction, alice)
    first_auction_bid_bob = house.auction_list(first_auction)[auction_struct.amount]

    init_alice = payment_token.balanceOf(alice)
    init_bob = payment_token.balanceOf(bob)
    init_house = payment_token.balanceOf(house)
    init_owner = payment_token.balanceOf(deployer)
    init_fee_receiver = payment_token.balanceOf(fee_receiver)
    assert init_bob == user_mint_amount - first_auction_bid_bob
    assert init_house == first_auction_bid_alice + first_auction_bid_bob

    # Audit state after second auction
    with boa.env.prank(deployer):
        house.create_new_auction()
    second_auction = house.auction_id()

    second_auction_bid_bob = house.default_reserve_price() * 3
    second_auction_bid_alice = house.default_reserve_price() * 4
    with boa.env.prank(bob):
        house.create_bid(second_auction, second_auction_bid_bob)
    with boa.env.prank(alice):
        house.create_bid(second_auction, second_auction_bid_alice)

    presettle_balance_bob = payment_token.balanceOf(bob)
    presettle_balance_alice = payment_token.balanceOf(alice)
    assert presettle_balance_bob == init_bob - second_auction_bid_bob
    assert presettle_balance_alice == init_alice - second_auction_bid_alice
    assert payment_token.balanceOf(deployer) == init_owner
    assert payment_token.balanceOf(fee_receiver) == init_fee_receiver

    # Settle auctions
    boa.env.time_travel(house.auction_remaining_time(second_auction) + 1)
    house.settle_auction(first_auction)
    house.settle_auction(second_auction)

    # Confirm auction settled
    assert house.is_auction_live(first_auction) is False
    assert house.is_auction_live(second_auction) is False
    assert house.auction_list(first_auction)[auction_struct.bidder] == bob
    assert house.auction_list(second_auction)[auction_struct.bidder] == alice
    assert house.auction_list(first_auction)[auction_struct.settled] is True
    assert house.auction_list(second_auction)[auction_struct.settled] is True

    # Settle auctions and confirm pending
    alice_pending = house.auction_pending_returns(
        first_auction, alice
    ) + house.auction_pending_returns(second_auction, alice)
    bob_pending = house.auction_pending_returns(first_auction, bob) + house.auction_pending_returns(
        second_auction, bob
    )
    assert alice_pending == first_auction_bid_alice
    assert bob_pending == second_auction_bid_bob

    with boa.env.prank(alice):
        house.withdraw(first_auction)
    with boa.env.prank(bob):
        house.withdraw(second_auction)

    alice_total_payment = house.auction_list(second_auction)[auction_struct.amount]
    bob_total_payment = house.auction_list(first_auction)[auction_struct.amount]

    # Calculate the expected fee and remaining amount for each auction
    alice_fee_amount = alice_total_payment * house.fee_percent() // precision
    alice_nonfee_amount = alice_total_payment - alice_fee_amount

    bob_fee_amount = bob_total_payment * house.fee_percent() // precision
    bob_nonfee_amount = bob_total_payment - bob_fee_amount

    final_alice = payment_token.balanceOf(alice)
    final_bob = payment_token.balanceOf(bob)
    final_house = payment_token.balanceOf(house)
    final_owner = payment_token.balanceOf(deployer)
    final_fee_receiver = payment_token.balanceOf(fee_receiver)

    # Assert that Alice's balance is reduced by the fee she paid
    assert final_alice == presettle_balance_alice + alice_pending
    assert final_alice == user_mint_amount - alice_total_payment

    # Assert that Bob's balance is reduced by the fee he paid
    assert final_bob == presettle_balance_bob + bob_pending
    assert final_bob == user_mint_amount - bob_total_payment

    # Assert that the deployer's balance has increased by the remaining amounts after fees
    assert final_owner == init_owner + alice_nonfee_amount + bob_nonfee_amount
    assert final_fee_receiver == init_fee_receiver + alice_fee_amount + bob_fee_amount
    assert final_house == 0


def test_balance_correct_on_dual_auction_split_wins_withdraw_multiple(
    auction_house_dual_bid,
    alice,
    bob,
    payment_token,
    deployer,
    approval_flags,
    fee_receiver,
    user_mint_amount,
    precision,
    auction_struct,
):
    house = auction_house_dual_bid
    first_auction = house.auction_id()
    first_auction_bid_alice = house.auction_pending_returns(first_auction, alice)
    first_auction_bid_bob = house.auction_list(first_auction)[auction_struct.amount]

    init_alice = payment_token.balanceOf(alice)
    init_bob = payment_token.balanceOf(bob)
    init_owner = payment_token.balanceOf(deployer)
    init_fee_receiver = payment_token.balanceOf(fee_receiver)

    with boa.env.prank(deployer):
        house.create_new_auction()
    second_auction = house.auction_id()

    second_auction_bid_bob = house.default_reserve_price() * 3
    second_auction_bid_alice = house.default_reserve_price() * 4
    with boa.env.prank(bob):
        house.create_bid(second_auction, second_auction_bid_bob)
    with boa.env.prank(alice):
        house.create_bid(second_auction, second_auction_bid_alice)

    presettle_balance_bob = payment_token.balanceOf(bob)
    presettle_balance_alice = payment_token.balanceOf(alice)
    assert presettle_balance_bob == init_bob - second_auction_bid_bob
    assert presettle_balance_alice == init_alice - second_auction_bid_alice
    assert payment_token.balanceOf(deployer) == init_owner
    assert payment_token.balanceOf(fee_receiver) == init_fee_receiver

    # Settle auctions
    boa.env.time_travel(house.auction_remaining_time(second_auction) + 1)
    house.settle_auction(first_auction)
    house.settle_auction(second_auction)

    # Confirm auction settled
    assert house.is_auction_live(first_auction) is False
    assert house.is_auction_live(second_auction) is False
    assert house.auction_list(first_auction)[auction_struct.bidder] == bob
    assert house.auction_list(second_auction)[auction_struct.bidder] == alice
    assert house.auction_list(first_auction)[auction_struct.settled] is True
    assert house.auction_list(second_auction)[auction_struct.settled] is True

    # Settle auctions
    alice_pending = house.auction_pending_returns(
        first_auction, alice
    ) + house.auction_pending_returns(second_auction, alice)
    bob_pending = house.auction_pending_returns(first_auction, bob) + house.auction_pending_returns(
        second_auction, bob
    )
    assert alice_pending == first_auction_bid_alice
    assert bob_pending == second_auction_bid_bob

    with boa.env.prank(alice):
        house.withdraw_multiple([first_auction, second_auction])
    with boa.env.prank(bob):
        house.withdraw_multiple([first_auction, second_auction])

    alice_total_payment = house.auction_list(second_auction)[auction_struct.amount]
    bob_total_payment = house.auction_list(first_auction)[auction_struct.amount]

    # Calculate the expected fee and remaining amount for each auction
    alice_fee_amount = alice_total_payment * house.fee_percent() // precision
    alice_nonfee_amount = alice_total_payment - alice_fee_amount

    bob_fee_amount = bob_total_payment * house.fee_percent() // precision
    bob_nonfee_amount = bob_total_payment - bob_fee_amount

    final_alice = payment_token.balanceOf(alice)
    final_bob = payment_token.balanceOf(bob)
    final_house = payment_token.balanceOf(house)
    final_owner = payment_token.balanceOf(deployer)
    final_fee_receiver = payment_token.balanceOf(fee_receiver)

    # Assert that Alice's balance is reduced by the fee she paid
    assert final_alice == presettle_balance_alice + alice_pending
    assert final_alice == user_mint_amount - second_auction_bid_alice
    assert final_alice == user_mint_amount - alice_total_payment

    # Assert that Bob's balance is reduced by the fee he paid
    assert final_bob == presettle_balance_bob + bob_pending
    assert final_bob == user_mint_amount - first_auction_bid_bob
    assert final_bob == user_mint_amount - bob_total_payment

    # Assert that the deployer's balance has increased by the remaining amounts after fees
    assert final_owner == init_owner + alice_nonfee_amount + bob_nonfee_amount
    assert final_fee_receiver == init_fee_receiver + alice_fee_amount + bob_fee_amount
    assert final_house == 0


def test_auction_settlement_throws_for_withdraw_all_on_bob_sweep(
    auction_house_dual_bid,
    alice,
    bob,
    payment_token,
    deployer,
    approval_flags,
    fee_receiver,
    user_mint_amount,
    precision,
    auction_struct,
):
    house = auction_house_dual_bid
    first_auction = house.auction_id()
    first_auction_bid_alice = house.auction_pending_returns(first_auction, alice)

    init_alice = payment_token.balanceOf(alice)
    init_bob = payment_token.balanceOf(bob)
    init_owner = payment_token.balanceOf(deployer)
    init_fee_receiver = payment_token.balanceOf(fee_receiver)

    with boa.env.prank(deployer):
        house.create_new_auction()
    second_auction = house.auction_id()

    second_auction_bid_bob = house.default_reserve_price() * 5
    second_auction_bid_alice = house.default_reserve_price() * 4

    # Bob wins both
    with boa.env.prank(alice):
        house.create_bid(second_auction, second_auction_bid_alice)
    with boa.env.prank(bob):
        house.create_bid(second_auction, second_auction_bid_bob)

    presettle_balance_bob = payment_token.balanceOf(bob)
    presettle_balance_alice = payment_token.balanceOf(alice)
    assert presettle_balance_bob == init_bob - second_auction_bid_bob
    assert presettle_balance_alice == init_alice - second_auction_bid_alice
    assert payment_token.balanceOf(deployer) == init_owner
    assert payment_token.balanceOf(fee_receiver) == init_fee_receiver

    # Settle auctions
    boa.env.time_travel(house.auction_remaining_time(second_auction) + 1)
    house.settle_auction(first_auction)
    house.settle_auction(second_auction)

    # Confirm auction settled
    assert house.is_auction_live(first_auction) is False
    assert house.is_auction_live(second_auction) is False
    assert house.auction_list(first_auction)[auction_struct.bidder] == bob
    assert house.auction_list(second_auction)[auction_struct.bidder] == bob
    assert house.auction_list(first_auction)[auction_struct.settled] is True
    assert house.auction_list(second_auction)[auction_struct.settled] is True

    # Confirm pending
    alice_pending = house.auction_pending_returns(
        first_auction, alice
    ) + house.auction_pending_returns(second_auction, alice)
    bob_pending = house.auction_pending_returns(
        second_auction, bob
    ) + house.auction_pending_returns(second_auction, bob)
    assert alice_pending == second_auction_bid_alice + first_auction_bid_alice
    assert bob_pending == 0

    with boa.env.prank(alice):
        house.withdraw_multiple([first_auction, second_auction])
    with boa.env.prank(bob):
        with boa.reverts("!pending"):
            house.withdraw_multiple([first_auction, second_auction])

    alice_total_payment = 0
    bob_total_payment = (
        house.auction_list(first_auction)[auction_struct.amount]
        + house.auction_list(second_auction)[auction_struct.amount]
    )

    # Calculate the expected fee and remaining amount for each auction
    alice_fee_amount = alice_total_payment * house.fee_percent() // precision
    alice_nonfee_amount = alice_total_payment - alice_fee_amount

    bob_fee_amount = bob_total_payment * house.fee_percent() // precision
    bob_nonfee_amount = bob_total_payment - bob_fee_amount

    final_alice = payment_token.balanceOf(alice)
    final_bob = payment_token.balanceOf(bob)
    final_house = payment_token.balanceOf(house)
    final_owner = payment_token.balanceOf(deployer)
    final_fee_receiver = payment_token.balanceOf(fee_receiver)

    # Assert that Alice's balance is reduced by the fee she paid
    assert final_alice == presettle_balance_alice + alice_pending
    assert final_alice == user_mint_amount

    # Assert that Bob's balance is reduced by the fee he paid
    assert final_bob == presettle_balance_bob
    assert final_bob == user_mint_amount - bob_total_payment

    # Assert that the deployer's balance has increased by the remaining amounts after fees
    assert final_owner == init_owner + alice_nonfee_amount + bob_nonfee_amount
    assert final_fee_receiver == init_fee_receiver + alice_fee_amount + bob_fee_amount
    assert final_house == 0

def test_can_withdraw_regular_without_settlement(
    auction_house_dual_bid,
    alice,
    bob,
    payment_token,
    deployer,
    approval_flags,
    fee_receiver,
    user_mint_amount,
    auction_struct,
):
    house = auction_house_dual_bid
    first_auction = house.auction_id()
    first_auction_bid_alice = house.auction_pending_returns(first_auction, alice)
    first_auction_bid_bob = house.auction_list(first_auction)[auction_struct.amount]

    init_alice = payment_token.balanceOf(alice)
    init_bob = payment_token.balanceOf(bob)
    init_owner = payment_token.balanceOf(deployer)
    init_fee_receiver = payment_token.balanceOf(fee_receiver)

    with boa.env.prank(deployer):
        house.create_new_auction()
    second_auction = house.auction_id()

    second_auction_bid_bob = house.default_reserve_price() * 3
    second_auction_bid_alice = house.default_reserve_price() * 4
    with boa.env.prank(bob):
        house.create_bid(second_auction, second_auction_bid_bob)
    with boa.env.prank(alice):
        house.create_bid(second_auction, second_auction_bid_alice)

    presettle_balance_bob = payment_token.balanceOf(bob)
    presettle_balance_alice = payment_token.balanceOf(alice)
    assert presettle_balance_bob == init_bob - second_auction_bid_bob
    assert presettle_balance_alice == init_alice - second_auction_bid_alice
    assert payment_token.balanceOf(deployer) == init_owner
    assert payment_token.balanceOf(fee_receiver) == init_fee_receiver

    # Finalize auctions
    boa.env.time_travel(house.auction_remaining_time(second_auction) + 1)

    # Confirm auction unsettled
    assert house.is_auction_live(first_auction) is False
    assert house.is_auction_live(second_auction) is False
    assert house.auction_list(first_auction)[auction_struct.bidder] == bob
    assert house.auction_list(second_auction)[auction_struct.bidder] == alice
    assert house.auction_list(first_auction)[auction_struct.settled] is False
    assert house.auction_list(second_auction)[auction_struct.settled] is False

    # Confirm pending
    alice_pending = house.auction_pending_returns(
        first_auction, alice
    ) + house.auction_pending_returns(second_auction, alice)
    bob_pending = house.auction_pending_returns(first_auction, bob) + house.auction_pending_returns(
        second_auction, bob
    )
    assert alice_pending == first_auction_bid_alice
    assert bob_pending == second_auction_bid_bob

    # Would generally work pre-settlement 
    with boa.env.anchor():
        with boa.env.prank(alice):
            house.withdraw(first_auction)
        with boa.env.prank(bob):
            house.withdraw(second_auction)
        assert payment_token.balanceOf(alice) != presettle_balance_alice
        assert payment_token.balanceOf(bob) != presettle_balance_bob

        with boa.env.prank(alice):
            with boa.reverts("!pending"):
                house.withdraw(second_auction)
        with boa.env.prank(bob):
            with boa.reverts("!pending"):
                house.withdraw(first_auction)

    # Calculate the expected fee and remaining amount for each auction
    final_alice = payment_token.balanceOf(alice)
    final_bob = payment_token.balanceOf(bob)
    final_house = payment_token.balanceOf(house)
    final_owner = payment_token.balanceOf(deployer)
    final_fee_receiver = payment_token.balanceOf(fee_receiver)

    # Assert that Alice's balance is correct
    assert final_alice == presettle_balance_alice
    assert final_alice == user_mint_amount - first_auction_bid_alice - second_auction_bid_alice

    # Assert that Bob's balance is correct
    assert final_bob == presettle_balance_bob
    assert final_bob == user_mint_amount - first_auction_bid_bob - second_auction_bid_bob

    # Assert that the deployer's balance is untouched
    assert final_owner == init_owner
    assert final_fee_receiver == init_fee_receiver
    assert (
        final_house
        == first_auction_bid_alice
        + first_auction_bid_bob
        + second_auction_bid_alice
        + second_auction_bid_bob
    )


def test_no_withdraw_multiple_without_settlement(
    auction_house_dual_bid,
    alice,
    bob,
    payment_token,
    deployer,
    approval_flags,
    fee_receiver,
    user_mint_amount,
    auction_struct,
):
    house = auction_house_dual_bid
    first_auction = house.auction_id()
    first_auction_bid_alice = house.auction_pending_returns(first_auction, alice)
    first_auction_bid_bob = house.auction_list(first_auction)[auction_struct.amount]

    init_alice = payment_token.balanceOf(alice)
    init_bob = payment_token.balanceOf(bob)
    init_owner = payment_token.balanceOf(deployer)
    init_fee_receiver = payment_token.balanceOf(fee_receiver)

    with boa.env.prank(deployer):
        house.create_new_auction()
    second_auction = house.auction_id()

    second_auction_bid_bob = house.default_reserve_price() * 3
    second_auction_bid_alice = house.default_reserve_price() * 4
    with boa.env.prank(bob):
        house.create_bid(second_auction, second_auction_bid_bob)
    with boa.env.prank(alice):
        house.create_bid(second_auction, second_auction_bid_alice)

    presettle_balance_bob = payment_token.balanceOf(bob)
    presettle_balance_alice = payment_token.balanceOf(alice)
    assert presettle_balance_bob == init_bob - second_auction_bid_bob
    assert presettle_balance_alice == init_alice - second_auction_bid_alice
    assert payment_token.balanceOf(deployer) == init_owner
    assert payment_token.balanceOf(fee_receiver) == init_fee_receiver

    # Settle auctions
    boa.env.time_travel(house.auction_remaining_time(second_auction) + 1)

    # Confirm auction unsettled
    assert house.is_auction_live(first_auction) is False
    assert house.is_auction_live(second_auction) is False
    assert house.auction_list(first_auction)[auction_struct.bidder] == bob
    assert house.auction_list(second_auction)[auction_struct.bidder] == alice
    assert house.auction_list(first_auction)[auction_struct.settled] is False
    assert house.auction_list(second_auction)[auction_struct.settled] is False

    # Settle auctions
    alice_pending = house.auction_pending_returns(
        first_auction, alice
    ) + house.auction_pending_returns(second_auction, alice)
    bob_pending = house.auction_pending_returns(first_auction, bob) + house.auction_pending_returns(
        second_auction, bob
    )
    assert alice_pending == first_auction_bid_alice
    assert bob_pending == second_auction_bid_bob

    # Should generally work if unsettled
    with boa.env.anchor():
        with boa.env.prank(alice):
            house.withdraw_multiple([first_auction, second_auction])
        with boa.env.prank(bob):
            house.withdraw_multiple([first_auction, second_auction])
        assert payment_token.balanceOf(alice) == presettle_balance_alice + alice_pending
        assert payment_token.balanceOf(bob) == presettle_balance_bob + bob_pending


    # Calculate the expected fee and remaining amount for each auction
    final_alice = payment_token.balanceOf(alice)
    final_bob = payment_token.balanceOf(bob)
    final_house = payment_token.balanceOf(house)
    final_owner = payment_token.balanceOf(deployer)
    final_fee_receiver = payment_token.balanceOf(fee_receiver)

    # Assert that Alice's balance is correct
    assert final_alice == presettle_balance_alice
    assert final_alice == user_mint_amount - first_auction_bid_alice - second_auction_bid_alice

    # Assert that Bob's balance is correct
    assert final_bob == presettle_balance_bob
    assert final_bob == user_mint_amount - first_auction_bid_bob - second_auction_bid_bob

    # Assert that the deployer's balance is untouched
    assert final_owner == init_owner
    assert final_fee_receiver == init_fee_receiver
    assert (
        final_house
        == first_auction_bid_alice
        + first_auction_bid_bob
        + second_auction_bid_alice
        + second_auction_bid_bob
    )

def test_withdrawal_security_with_rebidding(
    auction_house_with_auction,
    alice,
    bob,
    charlie,
    payment_token,
    default_reserve_price,
    zero_address,
    auction_struct,
):
    """
    Test to verify users cannot exploit the early withdrawal feature
    to withdraw more funds than they deposited through clever rebidding.

    Scenario:
    1. Alice bids with the minimum amount
    2. Bob outbids Alice
    3. Alice withdraws her returned funds
    4. Alice re-enters the auction with a new bid (using additional funds)
    5. Alice gets outbid and withdraws again

    This test ensures Alice can't somehow withdraw more than she put in through
    manipulation of the bidding and withdrawal system.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Track total deposits and withdrawals for Alice
    total_deposited = 0
    total_withdrawn = 0

    # Get initial balance
    initial_balance = payment_token.balanceOf(alice)

    # Step 1: Alice places initial bid
    alice_bid = default_reserve_price
    with boa.env.prank(alice):
        payment_token.approve(house.address, alice_bid)
        house.create_bid(auction_id, alice_bid)
    total_deposited += alice_bid

    # Step 2: Bob outbids Alice
    increment_percent = house.default_min_bid_increment_percentage()
    precision = 10**8

    # Calculate Bob's bid with correct precision
    bob_bid = alice_bid + (alice_bid * increment_percent // precision)

    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)

    # Verify auction state
    auction = house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == bob, "Bob should be highest bidder"
    assert house.pending_returns(alice) == alice_bid, "Alice should have pending returns"

    # Step 3: Alice withdraws her returned funds
    with boa.env.prank(alice):
        withdrawn = house.withdraw(auction_id)
        total_withdrawn += withdrawn

    # Verify Alice got her money back
    assert payment_token.balanceOf(alice) == initial_balance, "Alice should have received her funds back"
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns"

    # Step 4: Alice re-enters with a higher bid
    # Give Alice additional tokens to make a new bid
    alice_second_bid = bob_bid + (bob_bid * increment_percent // precision)
    payment_token._mint_for_testing(alice, alice_second_bid)

    with boa.env.prank(alice):
        payment_token.approve(house.address, alice_second_bid)
        house.create_bid(auction_id, alice_second_bid)
    total_deposited += alice_second_bid

    # Verify auction state
    auction = house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == alice, "Alice should now be highest bidder"
    assert house.pending_returns(bob) == bob_bid, "Bob should have pending returns"

    # Step 5: Charlie outbids Alice
    charlie_bid = alice_second_bid + (alice_second_bid * increment_percent // precision)
    with boa.env.prank(charlie):
        payment_token.approve(house.address, charlie_bid)
        house.create_bid(auction_id, charlie_bid)

    # Verify Alice now has pending returns
    assert house.pending_returns(alice) == alice_second_bid, "Alice should have her second bid in pending returns"

    # Step 6: Alice withdraws again
    with boa.env.prank(alice):
        withdrawn = house.withdraw(auction_id)
        total_withdrawn += withdrawn

    # This is the critical check: Alice shouldn't be able to withdraw more than she deposited
    assert total_withdrawn <= total_deposited, "Alice should not withdraw more than deposited"
    assert total_withdrawn == total_deposited, "Alice should be able to withdraw exactly what she deposited"

    # Verify Alice has no pending returns
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns after withdrawal"

    # Final check - verify Alice's balance is correct (initial + new tokens - net deposits)
    expected_balance = initial_balance + alice_second_bid - (total_deposited - total_withdrawn)
    assert payment_token.balanceOf(alice) == expected_balance, "Alice's balance should match expected"


def test_prevent_double_withdrawal_attack(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test that the contract prevents double withdrawal attacks by ensuring
    a user cannot withdraw the same funds twice even with early withdrawals enabled.
    This test simulates:
    1. Alice bids and gets outbid
    2. Alice withdraws her pending returns
    3. Alice attempts to withdraw again through various means
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = initial_bid + (initial_bid * min_increment // precision)
    
    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)
    
    # Step 2: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)
    
    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == initial_bid, "Alice should have pending returns"
    
    # Step 3: Alice withdraws her pending returns
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    
    # Verify Alice received her funds
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice should have received her funds back"
    assert house.pending_returns(alice) == 0, "Alice's pending returns should be cleared"
    
    # Step 4: Alice attempts to withdraw again - should fail
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
    
    # Step 5: Create a second auction to test if Alice can withdraw from wrong auction
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw_multiple([auction_id])
    
    # Verify Alice's balance hasn't changed from the initial withdrawal
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice's balance should remain unchanged after failed withdrawal attempts"
    
    # Step 6: Fast forward past auction end time to see if time affects withdrawal ability
    expiry_time = house.auction_remaining_time(auction_id) + 1
    boa.env.time_travel(seconds=expiry_time)
    
    # Step 7: Try to withdraw again after auction ends
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
    
    # Verify Alice's balance is still the same
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice's balance should remain unchanged"
    
    # Step 8: Try to withdraw after auction is settled
    house.settle_auction(auction_id)
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
    
    # Final verification that balance is unchanged
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice's balance should remain unchanged after all withdrawal attempts"


def test_prevent_front_running_withdrawal_attack(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
):
    """
    Test that the contract prevents front-running withdrawal attacks where
    a user monitors pending transactions and tries to withdraw funds just
    before being outbid. This simulates:
    1. Alice bids
    2. Bob prepares to outbid Alice
    3. Alice tries to withdraw (front-run) before Bob's bid is processed
    4. Bob's bid goes through
    5. Verify the state is correct
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = initial_bid + (initial_bid * min_increment // precision)
    
    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)
    
    # Step 2: In a real blockchain, this would be simulating Alice front-running Bob's transaction
    # We'll use a snapshot to simulate this sequence of events
    with boa.env.anchor():
        # Alice attempts to withdraw before actually being outbid
        with boa.env.prank(alice):
            with boa.reverts("!pending"):  # Should fail because Alice is the highest bidder
                house.withdraw(auction_id)
        
        # Alice's balance should be unchanged
        assert payment_token.balanceOf(alice) == initial_balance_alice - initial_bid, "Alice's balance should remain unchanged"
    
    # Step 3: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)
    
    # Step 4: Verify Alice now has pending returns
    assert house.pending_returns(alice) == initial_bid, "Alice should have pending returns after being outbid"
    
    # Step 5: Alice withdraws her pending returns legitimately
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    
    # Verify Alice received her funds
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice should have received her funds back"
    
    # Verify auction state is still correct
    auction = house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == bob, "Bob should still be the highest bidder"
    assert auction[auction_struct.amount] == second_bid, "Bid amount should remain unchanged"
    
    # Simulate another front-running attempt by Alice
    higher_bid = second_bid + (second_bid * min_increment // precision)
    
    # Step 6: Alice tries to withdraw again (would be front-running if this was a real pending tx)
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
    
    # Final verification
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice's balance should remain unchanged after failed withdrawal attempt"

def test_prevent_delegate_permission_abuse(
    auction_house_with_auction,
    alice,
    bob,
    charlie,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
    approval_flags,
):
    """
    Test that the contract prevents delegate permission abuse where
    a user might try to withdraw on behalf of another user without
    proper authorization. This test simulates:
    1. Alice bids and gets outbid
    2. Bob tries to withdraw Alice's funds without permission
    3. Alice grants Bob permission for withdrawals only
    4. Bob tries to bid on behalf of Alice (should fail)
    5. Bob withdraws on behalf of Alice (should succeed)
    6. Alice tries to withdraw again (should fail)
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    initial_balance_bob = payment_token.balanceOf(bob)

    # Calculate bid amounts
    initial_bid = default_reserve_price
    min_increment = house.default_min_bid_increment_percentage()
    charlie_bid = initial_bid + (initial_bid * min_increment // precision)

    # Step 1: Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, initial_bid)
        house.create_bid(auction_id, initial_bid)

    # Step 2: Charlie outbids Alice
    with boa.env.prank(charlie):
        payment_token.approve(house.address, charlie_bid)
        house.create_bid(auction_id, charlie_bid)

    # Verify Alice has pending returns
    assert house.pending_returns(alice) == initial_bid, "Alice should have pending returns"

    # Step 3: Bob tries to withdraw Alice's funds without permission
    with boa.env.prank(bob):
        with boa.reverts("!caller"):  # Should fail due to unauthorized caller
            house.withdraw(auction_id, alice)

    # Verify balances unchanged
    assert payment_token.balanceOf(alice) == initial_balance_alice - initial_bid, "Alice's balance should be unchanged"

    # Step 4: Alice grants Bob withdraw-only permission
    with boa.env.prank(alice):
        house.set_approved_caller(bob, approval_flags.WithdrawOnly)

    # Step 5: Bob tries to bid on behalf of Alice (should fail)
    bob_bid = charlie_bid + (charlie_bid * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        with boa.reverts("!caller"):  # Should fail due to wrong permission type
            house.create_bid(auction_id, bob_bid, "", alice)

    # Step 6: Bob successfully withdraws on behalf of Alice
    with boa.env.prank(bob):
        house.withdraw(auction_id, alice)

    # Verify Alice received her funds (not Bob)
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice should have received her funds back"
    assert payment_token.balanceOf(bob) == initial_balance_bob, "Bob's balance should be unchanged"

    # Step 7: Alice tries to withdraw again (should fail)
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)

    # Step 8: Bob tries to withdraw again on Alice's behalf (should fail)
    with boa.env.prank(bob):
        with boa.reverts("!pending"):
            house.withdraw(auction_id, alice)

    # Step 9: Test with full permissions
    with boa.env.prank(alice):
        house.set_approved_caller(bob, approval_flags.BidAndWithdraw)
        # Alice needs to approve the contract to spend her tokens
        payment_token.approve(house.address, bob_bid)

    # Now Bob should be able to bid on Alice's behalf with Alice's tokens
    with boa.env.prank(bob):
        # Bob doesn't need to approve since tokens come from Alice
        house.create_bid(auction_id, bob_bid, "", alice)

    # Verify auction state is updated correctly
    auction = house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == alice, "Alice should be the highest bidder"
    assert auction[auction_struct.amount] == bob_bid, "Bid amount should be updated"

    # Verify Charlie now has pending returns
    assert house.pending_returns(charlie) == charlie_bid, "Charlie should have pending returns"

    # Final verification
    assert payment_token.balanceOf(alice) == initial_balance_alice - bob_bid, "Alice's balance should reflect the new bid"



def test_withdraw_multiple_with_duplicates(
    auction_house_with_auction,
    alice,
    bob,
    deployer,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test to verify the contract's behavior when withdraw_multiple is called
    with duplicate auction IDs. This tests a potential vulnerability where
    a user might attempt to withdraw the same pending returns multiple times
    in a single transaction.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)
    
    # Bob outbids Alice
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)
    
    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == default_reserve_price, "Alice should have pending returns"
    
    # Attempt to double-withdraw by passing the same auction ID twice
    with boa.env.prank(alice):
        house.withdraw_multiple([auction_id, auction_id])
    
    # Check if Alice was able to withdraw more than she should have
    alice_final_balance = payment_token.balanceOf(alice)
    expected_final_balance = initial_balance_alice  # Should have received exactly her pending returns once
    
    print(f"Alice initial balance: {initial_balance_alice}")
    print(f"Alice final balance: {alice_final_balance}")
    print(f"Expected final balance: {expected_final_balance}")
    print(f"Difference: {alice_final_balance - expected_final_balance}")
    
    # The critical check - verify Alice didn't receive more than her pending returns
    assert alice_final_balance <= expected_final_balance, "Alice should not receive more than her pending returns"
    
    # Verify Alice has no more pending returns
    assert house.pending_returns(alice) == 0, "Alice should have no more pending returns"

def test_basic_reentrancy_protection(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Basic test to verify reentrancy protection in the withdrawal functions.
    The test simulates what would happen in a reentrancy attack by:
    1. Setting up a scenario where Alice has pending returns
    2. Verifying Alice can withdraw once successfully
    3. Confirming state is updated before external calls to prevent reentrancy
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Initial state tracking
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Alice makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)
    
    # Bob outbids Alice
    min_increment = house.default_min_bid_increment_percentage()
    second_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, second_bid)
        house.create_bid(auction_id, second_bid)
    
    # Verify Alice has pending returns
    pending_returns = house.pending_returns(alice)
    assert pending_returns == default_reserve_price, "Alice should have pending returns"
    
    # Simulate reentrancy: In a real attack, this would be a malicious token's callback
    # In this test, we check that state is updated before external calls
    with boa.env.prank(alice):
        # First withdrawal should succeed
        house.withdraw(auction_id)
        
        # If state is properly updated before external call, this should fail
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
    
    # Verify Alice's balance is correct - received exactly her pending returns once
    alice_final_balance = payment_token.balanceOf(alice)
    expected_final_balance = initial_balance_alice
    assert alice_final_balance == expected_final_balance, "Alice should receive her funds exactly once"
    
    # Verify pending returns are cleared
    assert house.auction_pending_returns(auction_id, alice) == 0, "Pending returns should be cleared"


def test_prevent_accounting_inconsistencies(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
    auction_struct,
):
    """
    Test that the contract maintains consistent accounting when a user
    is both a current high bidder and has pending returns from another auction.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Setup a second auction
    with boa.env.prank(house.owner()):
        second_auction_id = house.create_new_auction()
    
    # Track initial balances
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Alice bids on first auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)
    
    # Bob outbids Alice on first auction
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)
    
    # Verify Alice has pending returns on first auction
    assert house.pending_returns(alice) == default_reserve_price, "Alice should have pending returns from first auction"
    
    # Alice bids on second auction (becoming current high bidder there)
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(second_auction_id, default_reserve_price)
    
    # Verify Alice is high bidder on second auction
    second_auction = house.auction_list(second_auction_id)
    assert second_auction[auction_struct.bidder] == alice, "Alice should be high bidder on second auction"
    
    # Alice withdraws pending returns from first auction
    with boa.env.prank(alice):
        withdrawn = house.withdraw(auction_id)
        assert withdrawn == default_reserve_price, "Alice should withdraw her full bid from first auction"
    
    # Verify Alice's pending returns are now zero for first auction but still high bidder on second
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns from first auction"
    second_auction = house.auction_list(second_auction_id)
    assert second_auction[auction_struct.bidder] == alice, "Alice should still be high bidder on second auction"
    assert second_auction[auction_struct.amount] == default_reserve_price, "Alice's bid amount should be unchanged"
    
    # Bob outbids Alice on second auction
    bob_second_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_second_bid)
        house.create_bid(second_auction_id, bob_second_bid)
    
    # Verify Alice now has pending returns from second auction
    assert house.pending_returns(alice) == default_reserve_price, "Alice should have pending returns from second auction"
    
    # Alice withdraws from second auction
    with boa.env.prank(alice):
        withdrawn = house.withdraw(second_auction_id)
        assert withdrawn == default_reserve_price, "Alice should withdraw her full bid from second auction"
    
    # Final balance check - Alice should have same balance as she started with
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice's final balance should match initial balance"
    
    # Verify total accounting is consistent - Alice should have 0 pending returns
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns after withdrawals"


def test_prevent_rapid_cycling_manipulation(
    auction_house_with_auction,
    alice,
    bob,
    charlie,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test to prevent complex patterns of partial withdrawals and bids
    across multiple auctions that might enable manipulation.
    """
    house = auction_house_with_auction
    first_auction_id = house.auction_id()
    
    # Create two more auctions
    with boa.env.prank(house.owner()):
        second_auction_id = house.create_new_auction()
        third_auction_id = house.create_new_auction()
    
    # Track initial balances
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Calculate minimum bids with increments
    min_increment = house.default_min_bid_increment_percentage()
    outbid_amount = default_reserve_price + (default_reserve_price * min_increment // precision)
    
    # Step 1: Alice bids on first auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(first_auction_id, default_reserve_price)
    
    # Step 2: Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(house.address, outbid_amount)
        house.create_bid(first_auction_id, outbid_amount)
    
    # Step 3: Alice withdraws her returns
    with boa.env.prank(alice):
        house.withdraw(first_auction_id)
    
    # Step 4: Alice bids on second auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(second_auction_id, default_reserve_price)
    
    # Step 5: Charlie outbids Alice on second auction
    with boa.env.prank(charlie):
        payment_token.approve(house.address, outbid_amount)
        house.create_bid(second_auction_id, outbid_amount)
    
    # Step 6: Alice withdraws from second auction
    with boa.env.prank(alice):
        house.withdraw(second_auction_id)
    
    # Step 7: Alice bids on third auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(third_auction_id, default_reserve_price)
    
    # Step 8: Bob outbids Alice on third auction
    with boa.env.prank(bob):
        payment_token.approve(house.address, outbid_amount)
        house.create_bid(third_auction_id, outbid_amount)
    
    # Step 9: Alice withdraws from third auction
    with boa.env.prank(alice):
        house.withdraw(third_auction_id)
    
    # Calculate total funds Alice has put in versus taken out
    total_spent = default_reserve_price * 3  # Bid on three auctions
    total_withdrawn = default_reserve_price * 3  # Withdrew from three auctions
    
    # Alice should be back at her initial balance after this rapid cycling
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice's balance should return to initial after cycle"
    
    # Alice should have zero pending returns
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns"
    
    # Skip forward and settle all auctions
    expiry_time = max(
        house.auction_remaining_time(first_auction_id),
        house.auction_remaining_time(second_auction_id),
        house.auction_remaining_time(third_auction_id)
    ) + 1
    boa.env.time_travel(seconds=expiry_time)
    
    house.settle_auction(first_auction_id)
    house.settle_auction(second_auction_id)
    house.settle_auction(third_auction_id)
    
    # Final check - Alice still cannot withdraw anything more
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw_multiple([first_auction_id, second_auction_id, third_auction_id])
    
    assert payment_token.balanceOf(alice) == initial_balance_alice, "Alice's final balance should match initial"


def test_prevent_status_tracking_bypass(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test that withdraw_multiple properly handles auction status and
    prevents withdrawals from non-settled auctions when appropriate.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Create a second auction
    with boa.env.prank(house.owner()):
        second_auction_id = house.create_new_auction()
    
    # Alice bids on first auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)
    
    # Bob outbids Alice on first auction
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)
    
    # Alice bids on second auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(second_auction_id, default_reserve_price)
    
    # Bob outbids Alice on second auction
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(second_auction_id, bob_bid)
    
    # End auctions but don't settle
    expiry_time = max(
        house.auction_remaining_time(auction_id),
        house.auction_remaining_time(second_auction_id)
    ) + 1
    boa.env.time_travel(seconds=expiry_time)
    
    # Try to withdraw from both auctions
    first_pending = house.auction_pending_returns(auction_id, alice)
    second_pending = house.auction_pending_returns(second_auction_id, alice)
    initial_balance_alice = payment_token.balanceOf(alice)
    
    # Verify Alice has pending returns in both auctions
    assert first_pending == default_reserve_price, "Alice should have pending returns from first auction"
    assert second_pending == default_reserve_price, "Alice should have pending returns from second auction"
    
    # Withdraw from first auction directly
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    
    # Withdraw from second auction directly
    with boa.env.prank(alice):
        house.withdraw(second_auction_id)
    
    # Alice should have received both withdrawals
    assert payment_token.balanceOf(alice) == initial_balance_alice + first_pending + second_pending, "Alice should receive both withdrawals"
    
    # Alice should have no pending returns
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns"
    
    # Try withdraw_multiple now that balances are cleared
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw_multiple([auction_id, second_auction_id])
    
    # Now settle the auctions
    house.settle_auction(auction_id)
    house.settle_auction(second_auction_id)
    
    # Try to withdraw again - should still fail
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
        with boa.reverts("!pending"):
            house.withdraw(second_auction_id)
        with boa.reverts("!pending"):
            house.withdraw_multiple([auction_id, second_auction_id])


def test_prevent_array_manipulation_attacks(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test that withdraw_multiple cannot be exploited through array manipulations
    like duplicate entries to withdraw more than allocated.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    # Create two more auctions
    with boa.env.prank(house.owner()):
        second_auction_id = house.create_new_auction()
        third_auction_id = house.create_new_auction()

    # Alice bids on all three auctions
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 3)
        house.create_bid(auction_id, default_reserve_price)
        house.create_bid(second_auction_id, default_reserve_price)
        house.create_bid(third_auction_id, default_reserve_price)

    # Bob outbids Alice on all auctions
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid * 3)
        house.create_bid(auction_id, bob_bid)
        house.create_bid(second_auction_id, bob_bid)
        house.create_bid(third_auction_id, bob_bid)

    # Record initial state
    initial_balance_alice = payment_token.balanceOf(alice)
    total_pending = house.pending_returns(alice)
    assert total_pending == default_reserve_price * 3, "Alice should have pending returns from all three auctions"

    # Try to withdraw with duplicate auction IDs in the array
    with boa.env.prank(alice):
        # Should only handle unique auctions
        house.withdraw_multiple([auction_id, auction_id, auction_id, second_auction_id, second_auction_id, third_auction_id])

    # Verify Alice received exactly the right amount despite duplicate entries
    expected_withdrawal = default_reserve_price * 3
    assert payment_token.balanceOf(alice) == initial_balance_alice + expected_withdrawal, "Alice should receive exactly the correct amount despite duplicates"

    # Verify pending returns are zero
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns"

    # Try to withdraw again using withdraw_multiple
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw_multiple([auction_id, second_auction_id, third_auction_id])

def test_transfer_failure_handling(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test that the contract safely handles token transfer failures during withdrawals.
    Note: This is a limited test since we can't easily modify the token contract
    behavior in our testing environment.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Alice bids on auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)
    
    # Bob outbids Alice
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)
    
    # Verify Alice has pending returns
    assert house.pending_returns(alice) == default_reserve_price, "Alice should have pending returns"
    
    # Alice withdraws her pending returns
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    
    # Verify Alice has no more pending returns
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns after withdrawal"
    
    # Verify withdrawal was processed only once
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)

def test_timing_based_attacks(
    auction_house_with_auction,
    alice,
    bob,
    payment_token,
    default_reserve_price,
    precision,
):
    """
    Test that the contract is secure against timing-based attacks
    around auction end times.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Alice bids on auction
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)
    
    # Bob outbids Alice
    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)
    with boa.env.prank(bob):
        payment_token.approve(house.address, bob_bid)
        house.create_bid(auction_id, bob_bid)
    
    # Record Alice's balance and pending returns
    initial_balance_alice = payment_token.balanceOf(alice)
    pending_returns = house.pending_returns(alice)
    assert pending_returns == default_reserve_price, "Alice should have pending returns"
    
    # Time travel to just before auction end
    auction_remaining = house.auction_remaining_time(auction_id)
    boa.env.time_travel(seconds=auction_remaining - 1)
    
    # Alice withdraws just before auction ends
    with boa.env.prank(alice):
        house.withdraw(auction_id)
    
    # Verify Alice received her funds
    assert payment_token.balanceOf(alice) == initial_balance_alice + pending_returns, "Alice should receive her pending returns"
    assert house.pending_returns(alice) == 0, "Alice should have no pending returns"
    
    # Time travel past auction end
    boa.env.time_travel(seconds=2)
    assert house.is_auction_live(auction_id) is False, "Auction should have ended"
    
    # Try to withdraw again or rebid
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
        
        # Try to rebid at the last moment
        payment_token.approve(house.address, bob_bid * 2)
        with boa.reverts("expired"):
            house.create_bid(auction_id, bob_bid * 2)
    
    # Settle the auction
    house.settle_auction(auction_id)
    
    # Verify no further withdrawals are possible
    with boa.env.prank(alice):
        with boa.reverts("!pending"):
            house.withdraw(auction_id)
