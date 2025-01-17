import pytest
import boa

def test_withdraw_stale(auction_house_with_auction, deployer, proceeds_receiver, alice, bob, payment_token):
    """Test admin withdrawal of stale pending returns"""
    balance_of_alice_before = payment_token.balanceOf(alice)
    balance_of_deployer_before = payment_token.balanceOf(deployer)
    balance_of_proceeds_before = payment_token.balanceOf(proceeds_receiver)
    
    auction_id = auction_house_with_auction.auction_id()
    
    # Create pending returns
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 200)
        auction_house_with_auction.create_bid(auction_id, 200)
    
    # Fast forward and settle
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)
    
    # Check balances after settlement
    assert payment_token.balanceOf(deployer) == balance_of_deployer_before + 10  # 5% of 200
    assert payment_token.balanceOf(proceeds_receiver) == balance_of_proceeds_before + 190  # 95% of 200
    assert payment_token.balanceOf(alice) == balance_of_alice_before - 100
    assert auction_house_with_auction.pending_returns(alice) == 100
    
    # Admin withdraws stale returns
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice])
    
    # Verify final states
    assert auction_house_with_auction.pending_returns(alice) == 0
    assert payment_token.balanceOf(alice) == balance_of_alice_before - 5  # Alice gets original bid - 5% penalty
    assert payment_token.balanceOf(deployer) == balance_of_deployer_before + 15  # Original 5% + 5% penalty

def test_withdraw_stale_multiple_users(auction_house_with_auction, alice, bob, charlie, deployer, payment_token):
    """Test admin withdrawal for multiple users with various states"""
    balance_alice_before = payment_token.balanceOf(alice)
    balance_bob_before = payment_token.balanceOf(bob)
    balance_charlie_before = payment_token.balanceOf(charlie)
    balance_deployer_before = payment_token.balanceOf(deployer)
    
    auction_id = auction_house_with_auction.auction_id()
    
    # Bob bids first
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    # Charlie wins with higher bid
    with boa.env.prank(charlie):
        payment_token.approve(auction_house_with_auction.address, 200)
        auction_house_with_auction.create_bid(auction_id, 200)
    
    # Settle auction
    boa.env.time_travel(seconds=4000)
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)
    
    # Admin withdraws stale returns for all users
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice, bob, charlie])
    
    # Alice had no pending returns
    assert payment_token.balanceOf(alice) == balance_alice_before
    
    # Bob gets his bid back minus 5% fee
    assert auction_house_with_auction.pending_returns(bob) == 0
    assert payment_token.balanceOf(bob) == balance_bob_before - 5  # Original 100 - 5% fee
    
    # Charlie spent his bid as winner
    assert auction_house_with_auction.pending_returns(charlie) == 0
    assert payment_token.balanceOf(charlie) == balance_charlie_before - 200
    
    # Deployer got the fees
    assert payment_token.balanceOf(deployer) == balance_deployer_before + 15  # 5% of 200 + 5% of 100

def test_create_bid_with_pending_returns(auction_house_with_auction, alice, bob, payment_token):
    """Test using pending returns for a new bid"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 106)
        auction_house_with_auction.create_bid(auction_id, 106)
    
    assert auction_house_with_auction.pending_returns(alice) == 100
    
    # Alice uses pending returns plus additional tokens for new higher bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 25)  # Need to approve the extra amount
        auction_house_with_auction.create_bid(auction_id, 125)  # Uses 100 from pending + 25 new
    
    auction = auction_house_with_auction.auction_list(auction_id)
    assert auction[4] == alice  # bidder
    assert auction[1] == 125  # amount
    assert auction_house_with_auction.pending_returns(alice) == 0  # Used up pending returns

def test_create_bid_insufficient_pending_returns(auction_house_with_auction, alice, bob, payment_token):
    """Test bid fails when pending returns aren't enough"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 106)
        auction_house_with_auction.create_bid(auction_id, 106)
    
    # Alice tries to bid too high with insufficient returns and insufficient approval
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 25)  # Not enough approval
        with boa.reverts():  # Expected to fail on token transfer
            auction_house_with_auction.create_bid(auction_id, 200)
    
    # State should be unchanged
    auction = auction_house_with_auction.auction_list(auction_id)
    assert auction[4] == bob  # still bob's bid
    assert auction[1] == 106  # amount unchanged
    assert auction_house_with_auction.pending_returns(alice) == 100  # returns unchanged
