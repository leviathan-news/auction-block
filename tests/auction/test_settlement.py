import pytest
import boa

def create_pending_returns(auction_house, bidder_1, bidder_2):
    """Helper function to create pending returns"""
    with boa.env.prank(bidder_1):
        auction_house.create_bid(1, 100, value=100)
    with boa.env.prank(bidder_2):
        auction_house.create_bid(1, 200, value=200)

def test_withdraw_after_outbid(auction_house_with_auction, alice, bob):
    """Test withdrawing funds after being outbid"""
    # Track initial balance
    alice_balance_before = boa.env.get_balance(alice)
    
    # First bid from alice
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(1, 100, value=100)
    
    # Bob outbids
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(1, 200, value=200)
    
    # Alice should have pending returns
    assert auction_house_with_auction.pending_returns(alice) == 100
    
    # Alice withdraws
    with boa.env.prank(alice):
        auction_house_with_auction.withdraw()
    
    # Check alice got her funds back
    alice_balance_after = boa.env.get_balance(alice)
    assert alice_balance_after == alice_balance_before, "Alice should get her bid back"

def test_withdraw_zero_pending(auction_house_with_auction, alice):
    """Test withdrawing with no pending returns"""
    balance_before = boa.env.get_balance(alice)
    
    with boa.env.prank(alice):
        auction_house_with_auction.withdraw()
    
    balance_after = boa.env.get_balance(alice)
    assert balance_after == balance_before

def test_settle_auction_no_bids(auction_house_with_auction, deployer):
    """Test settling an auction with no bids"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Fast forward past auction end
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_auction(auction_id)
    
    auction = auction_house_with_auction.auction_list(auction_id)
    assert auction[5] == True  # settled

def test_settle_auction_with_single_bid(auction_house_with_auction, alice, deployer, proceeds_receiver):
    """Test settling auction with one bid"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Track balances before
    deployer_balance_before = boa.env.get_balance(deployer)
    proceeds_receiver_balance_before = boa.env.get_balance(proceeds_receiver)
    
    # Place bid
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, 100, value=100)
    
    # Fast forward and settle
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_auction(auction_id)
    
    # Check balances after
    deployer_balance_after = boa.env.get_balance(deployer)
    proceeds_receiver_balance_after = boa.env.get_balance(proceeds_receiver)
    
    # Owner should get 5% of 100 = 5
    assert deployer_balance_after - deployer_balance_before == 5
    # Proceeds receiver should get 95% of 100 = 95
    assert proceeds_receiver_balance_after - proceeds_receiver_balance_before == 95

def test_settle_multiple_bids(auction_house_with_auction, alice, bob, deployer, proceeds_receiver):
    """Test settling with multiple bids"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Track initial balances
    alice_balance_before = boa.env.get_balance(alice)
    deployer_balance_before = boa.env.get_balance(deployer)
    proceeds_receiver_balance_before = boa.env.get_balance(proceeds_receiver)
    
    # Place bids
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, 100, value=100)
    
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(auction_id, 1000, value=1000)
    
    # Fast forward and settle
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_auction(auction_id)
    
    # Check balances
    alice_balance_mid = boa.env.get_balance(alice)
    assert alice_balance_mid == alice_balance_before - 100  # Alice's bid is pending return
    
    # Alice withdraws
    with boa.env.prank(alice):
        auction_house_with_auction.withdraw()
    
    alice_balance_after = boa.env.get_balance(alice)
    assert alice_balance_after == alice_balance_before  # Alice got her bid back
    
    # Check fee distribution from Bob's winning bid
    deployer_balance_after = boa.env.get_balance(deployer)
    proceeds_receiver_balance_after = boa.env.get_balance(proceeds_receiver)
    
    assert deployer_balance_after - deployer_balance_before == 50  # 5% of 1000
    assert proceeds_receiver_balance_after - proceeds_receiver_balance_before == 950  # 95% of 1000

def test_settle_auction_not_ended(auction_house_with_auction, deployer):
    """Test cannot settle auction before it ends"""
    auction_id = auction_house_with_auction.auction_id()
    
    with boa.env.prank(deployer), boa.reverts("Auction hasn't completed"):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_auction(auction_id)

def test_auction_extension(auction_house_with_auction, alice, bob):
    """Test auction gets extended when bid near end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Place initial bid
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, 100, value=100)
    
    # Move to near end of auction
    auction = auction_house_with_auction.auction_list(auction_id)
    time_to_move = auction[3] - auction[2] - 50  # end_time - start_time - 50 seconds
    boa.env.time_travel(seconds=int(time_to_move))
    
    # Place bid near end
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(auction_id, 200, value=200)
    
    # Check auction was extended
    new_auction = auction_house_with_auction.auction_list(auction_id)
    assert new_auction[3] > auction[3]  # new end_time > old end_time
