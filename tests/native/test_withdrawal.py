import pytest
import boa
from eth_utils import to_wei

def test_withdraw_stale(
    auction_house_with_auction, 
    deployer, 
    proceeds_receiver, 
    alice, 
    bob, 
    payment_token, 
    default_reserve_price,
    default_split_percentage
):
    """Test admin withdrawal of stale pending returns"""
    balance_of_alice_before = payment_token.balanceOf(alice)
    balance_of_deployer_before = payment_token.balanceOf(deployer)
    balance_of_proceeds_before = payment_token.balanceOf(proceeds_receiver)
    
    auction_id = auction_house_with_auction.auction_id()
    
    # Create pending returns
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        auction_house_with_auction.create_bid(auction_id, default_reserve_price)
    
    # Calculate minimum next bid
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    next_bid = default_reserve_price + (default_reserve_price * min_increment) // 100
    
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, next_bid)
        auction_house_with_auction.create_bid(auction_id, next_bid)
    
    # Fast forward and settle
    boa.env.time_travel(seconds=4000)
    
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)
    
    # Verify pending returns before stale withdrawal
    assert auction_house_with_auction.pending_returns(alice) == default_reserve_price
    
    # Admin withdraws stale returns
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice])
    
    # Calculate expected amounts after stale withdrawal
    stale_fee = default_reserve_price * 5 // 100  # 5% penalty on stale withdraw
    alice_return = default_reserve_price - stale_fee  # Original bid minus penalty
    
    # Calculate auction proceeds
    winner_bid_owner_share = next_bid - (next_bid * default_split_percentage // 100)  # Owner's share of winning bid 
    winner_bid_proceeds = next_bid * default_split_percentage // 100  # Proceeds receiver's share
    
    # Verify final states
    assert auction_house_with_auction.pending_returns(alice) == 0
    assert payment_token.balanceOf(alice) == balance_of_alice_before + alice_return - default_reserve_price
    assert payment_token.balanceOf(deployer) == balance_of_deployer_before + winner_bid_owner_share + stale_fee
    assert payment_token.balanceOf(proceeds_receiver) == balance_of_proceeds_before + winner_bid_proceeds
def test_withdraw_stale_multiple_users(auction_house_with_auction, alice, bob, charlie, deployer, payment_token, default_reserve_price):
    """Test admin withdrawal for multiple users with various states"""
    balance_alice_before = payment_token.balanceOf(alice)
    balance_bob_before = payment_token.balanceOf(bob)
    balance_charlie_before = payment_token.balanceOf(charlie)
    balance_deployer_before = payment_token.balanceOf(deployer)
    
    auction_id = auction_house_with_auction.auction_id()
    
    # Calculate bid amounts
    first_bid = default_reserve_price
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    second_bid = first_bid + (first_bid * min_increment) // 100
    
    # Bob bids first
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, first_bid)
        auction_house_with_auction.create_bid(auction_id, first_bid)
    
    # Charlie wins with higher bid
    with boa.env.prank(charlie):
        payment_token.approve(auction_house_with_auction.address, second_bid)
        auction_house_with_auction.create_bid(auction_id, second_bid)
    
    # Settle auction
    boa.env.time_travel(seconds=4000)
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(auction_id)
    
    # Admin withdraws stale returns for all users
    with boa.env.prank(deployer):
        auction_house_with_auction.withdraw_stale([alice, bob, charlie])
    
    # Calculate fees
    bob_fee = (first_bid * 5) // 100  # 5% fee on Bob's outbid amount
    deployer_fee = bob_fee  # Only getting fee from Bob's withdrawal
    
    # Verify final balances
    assert payment_token.balanceOf(alice) == balance_alice_before  # No change
    assert payment_token.balanceOf(bob) == balance_bob_before - first_bid + (first_bid - bob_fee)  # Gets back bid minus fee
    assert payment_token.balanceOf(charlie) == balance_charlie_before - second_bid  # Paid winning bid
    assert payment_token.balanceOf(deployer) == balance_deployer_before + deployer_fee  # Got fees

def test_create_bid_with_pending_returns(auction_house_with_auction, alice, bob, payment_token, default_reserve_price):
    """Test using pending returns for a new bid"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    
    # Calculate bid amounts
    initial_bid = default_reserve_price
    bob_bid = initial_bid + (initial_bid * min_increment) // 100
    final_bid = bob_bid + (bob_bid * min_increment) // 100
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
    assert auction[4] == alice  # bidder
    assert auction[1] == final_bid  # amount
    assert auction_house_with_auction.pending_returns(alice) == 0  # Used up pending returns

def test_create_bid_insufficient_pending_returns(auction_house_with_auction, alice, bob, payment_token, default_reserve_price):
    """Test bid fails when pending returns aren't enough"""
    auction_id = auction_house_with_auction.auction_id()
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    
    # Calculate bid amounts
    initial_bid = default_reserve_price
    bob_bid = initial_bid + (initial_bid * min_increment) // 100
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
    assert auction[4] == bob  # still bob's bid
    assert auction[1] == bob_bid  # amount unchanged
    assert auction_house_with_auction.pending_returns(alice) == initial_bid
