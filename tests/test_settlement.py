import pytest
import boa

def test_withdraw_after_outbid(auction_house_with_auction, alice, bob, payment_token):
    """Test withdrawing funds after being outbid"""
    # Track initial balance
    alice_balance_before = payment_token.balanceOf(alice)
    
    # First bid from alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(1, 100)
    
    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 200)
        auction_house_with_auction.create_bid(1, 200)
    
    # Alice should have pending returns
    assert auction_house_with_auction.pending_returns(alice) == 100
    
    # Alice withdraws
    with boa.env.prank(alice):
        auction_house_with_auction.withdraw()
    
    # Check alice got her funds back
    alice_balance_after = payment_token.balanceOf(alice)
    assert alice_balance_after == alice_balance_before, "Alice should get her bid back"

def test_withdraw_zero_pending(auction_house_with_auction, alice, payment_token):
    """Test withdrawing with no pending returns"""
    balance_before = payment_token.balanceOf(alice)
    
    with boa.env.prank(alice), boa.reverts("No pending returns"):
        auction_house_with_auction.withdraw()
    
    balance_after = payment_token.balanceOf(alice)
    assert balance_after == balance_before

def test_settle_auction_no_bids(auction_house_with_auction, deployer):
    """Test settling an auction with no bids"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Get initial state
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    print(f"Initial auction state: {initial_auction}")
    
    # Fast forward past auction end
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)
    
    # Get final state
    final_auction = auction_house_with_auction.auction_list(auction_id)
    new_auction = auction_house_with_auction.auction_list(auction_id + 1)
    print(f"Final auction state: {final_auction}")
    print(f"New auction state: {new_auction}")
    print(f"New auction ID: {auction_house_with_auction.auction_id()}")
    
    # Verify auction was settled and new one created
    assert auction_house_with_auction.auction_id() == auction_id + 1
    assert final_auction[5] == True  # settled
    assert new_auction[0] == auction_id + 1  # new auction has correct ID

def test_settle_auction_with_single_bid(auction_house_with_auction, alice, deployer, proceeds_receiver, payment_token):
    """Test settling auction with one bid"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Track balances before
    deployer_balance_before = payment_token.balanceOf(deployer)
    proceeds_receiver_balance_before = payment_token.balanceOf(proceeds_receiver)
    
    # Place bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    # Fast forward and settle
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)
    
    # Check balances after
    deployer_balance_after = payment_token.balanceOf(deployer)
    proceeds_receiver_balance_after = payment_token.balanceOf(proceeds_receiver)
    
    # Owner should get 5% of 100 = 5
    assert deployer_balance_after - deployer_balance_before == 5
    # Proceeds receiver should get 95% of 100 = 95
    assert proceeds_receiver_balance_after - proceeds_receiver_balance_before == 95

def test_settle_multiple_bids(auction_house_with_auction, alice, bob, deployer, proceeds_receiver, payment_token):
    """Test settling with multiple bids"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Track initial balances
    alice_balance_before = payment_token.balanceOf(alice)
    deployer_balance_before = payment_token.balanceOf(deployer)
    proceeds_receiver_balance_before = payment_token.balanceOf(proceeds_receiver)
    
    # Place bids
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 1000)
        auction_house_with_auction.create_bid(auction_id, 1000)
    
    # Fast forward and settle
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)
    
    # Check balances
    alice_balance_mid = payment_token.balanceOf(alice)
    assert alice_balance_mid == alice_balance_before - 100  # Alice's bid is pending return
    
    # Alice withdraws
    with boa.env.prank(alice):
        auction_house_with_auction.withdraw()
    
    alice_balance_after = payment_token.balanceOf(alice)
    assert alice_balance_after == alice_balance_before  # Alice got her bid back
    
    # Check fee distribution from Bob's winning bid
    deployer_balance_after = payment_token.balanceOf(deployer)
    proceeds_receiver_balance_after = payment_token.balanceOf(proceeds_receiver)
    
    assert deployer_balance_after - deployer_balance_before == 50  # 5% of 1000
    assert proceeds_receiver_balance_after - proceeds_receiver_balance_before == 950  # 95% of 1000

def test_settle_auction_not_ended(auction_house_with_auction, deployer):
    """Test cannot settle auction before it ends"""
    auction_id = auction_house_with_auction.auction_id()
    
    with boa.env.prank(deployer), boa.reverts("Auction hasn't completed"):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)

def test_auction_extension(auction_house_with_auction, alice, bob, payment_token):
    """Test auction gets extended when bid near end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Place initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    # Move to near end of auction
    auction = auction_house_with_auction.auction_list(auction_id)
    time_to_move = auction[3] - auction[2] - 50  # end_time - start_time - 50 seconds
    boa.env.time_travel(seconds=int(time_to_move))
    
    # Place bid near end
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 200)
        auction_house_with_auction.create_bid(auction_id, 200)
    
    # Check auction was extended
    new_auction = auction_house_with_auction.auction_list(auction_id)
    assert new_auction[3] > auction[3]  # new end_time > old end_time
