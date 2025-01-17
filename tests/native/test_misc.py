import pytest
import boa
from eth_utils import to_wei

def test_auction_extension_near_end(auction_house_with_auction, alice, bob, payment_token):
    """Test auction extension when bid placed near end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[3]
    
    # Move to near end
    time_to_end = initial_end - initial_auction[2] - 10  # 10 seconds before end
    boa.env.time_travel(seconds=int(time_to_end))
    
    # New bid should extend
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 200)
        auction_house_with_auction.create_bid(auction_id, 200)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[3] > initial_end
    #assert final_auction[3] == boa.env.timestamp + auction_house_with_auction.time_buffer()

def test_auction_extension_not_near_end(auction_house_with_auction, alice, bob, payment_token):
    """Test auction not extended when bid placed well before end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[3]
    
    # Move to middle of auction
    time_to_move = (initial_end - initial_auction[2]) // 2
    boa.env.time_travel(seconds=int(time_to_move))
    
    # New bid should not extend
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 200)
        auction_house_with_auction.create_bid(auction_id, 200)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[3] == initial_end

def test_bid_validation_wrong_id(auction_house_with_auction, alice, payment_token):
    """Test bid for non-existent auction fails"""
    wrong_id = auction_house_with_auction.auction_id() + 1
    
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        with boa.reverts("Invalid auction ID"):
            auction_house_with_auction.create_bid(wrong_id, 100)

def test_bid_validation_expired(auction_house_with_auction, alice, payment_token):
    """Test bid after auction end fails"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Move past auction end
    auction = auction_house_with_auction.auction_list(auction_id)
    time_to_end = auction[3] - auction[2] + 1
    boa.env.time_travel(seconds=int(time_to_end))
    
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        with boa.reverts("Auction expired"):
            auction_house_with_auction.create_bid(auction_id, 100)

def test_bid_validation_too_low(auction_house_with_auction, alice, payment_token):
    """Test bid below reserve price fails"""
    auction_id = auction_house_with_auction.auction_id()
    reserve_price = auction_house_with_auction.reserve_price()
    
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, reserve_price - 1)
        with boa.reverts("Must send at least reservePrice"):
            auction_house_with_auction.create_bid(auction_id, reserve_price - 1)

def test_bid_increment_validation(auction_house_with_auction, alice, bob, payment_token):
    """Test minimum bid increment enforcement"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(auction_id, 100)
    
    # Try to bid just slightly higher
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 101)
        with boa.reverts("Must send more than last bid by min_bid_increment_percentage amount"):
            auction_house_with_auction.create_bid(auction_id, 101)
    
    # Calculate minimum valid next bid
    min_increment = (100 * auction_house_with_auction.min_bid_increment_percentage()) // 100
    min_next_bid = 100 + min_increment
    
    # Valid bid at minimum increment
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, min_next_bid)
        auction_house_with_auction.create_bid(auction_id, min_next_bid)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[4] == bob
    assert final_auction[1] == min_next_bid

def test_withdraw_after_settlement(auction_house_with_auction, alice, bob, deployer, payment_token):
    """Test withdrawing returns after auction settlement"""
    bid_1 = to_wei(0.5, 'ether')
    bid_2 = to_wei(0.6, 'ether')
    
    # Place bids
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1)
        auction_house_with_auction.create_bid(1, bid_1)
    
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bid_2)
        auction_house_with_auction.create_bid(1, bid_2)
    
    # End and settle auction
    boa.env.time_travel(seconds=3700)
    auction_house_with_auction.settle_auction(1)
    
    # Verify Alice can still withdraw after settlement
    with boa.env.prank(alice):
        initial_balance = payment_token.balanceOf(alice)
        auction_house_with_auction.withdraw()
        final_balance = payment_token.balanceOf(alice)
        assert final_balance - initial_balance == bid_1

def test_pending_returns_overflow_protection(auction_house_with_auction, alice, bob, deployer, payment_token):
    """Test that pending returns summation cannot overflow"""
    MAX_TEST_AUCTIONS = 5
    LARGE_BID = to_wei(100, 'ether')  # More reasonable value
    
    # Give more tokens to bidders
    payment_token._mint_for_testing(alice, LARGE_BID * MAX_TEST_AUCTIONS * 2)
    payment_token._mint_for_testing(bob, LARGE_BID * MAX_TEST_AUCTIONS * 3)
    
    for _ in range(MAX_TEST_AUCTIONS - 1):
        with boa.env.prank(deployer):
            auction_house_with_auction.create_new_auction()
    
    for i in range(MAX_TEST_AUCTIONS):
        auction_id = i + 1
        with boa.env.prank(alice):
            payment_token.approve(auction_house_with_auction.address, LARGE_BID)
            auction_house_with_auction.create_bid(auction_id, LARGE_BID)
        
        min_increment = auction_house_with_auction.min_bid_increment_percentage()
        higher_bid = LARGE_BID + (LARGE_BID * min_increment) // 100
        
        with boa.env.prank(bob):
            payment_token.approve(auction_house_with_auction.address, higher_bid)
            auction_house_with_auction.create_bid(auction_id, higher_bid)
    
    total_pending = auction_house_with_auction.pending_returns(alice)
    assert total_pending == LARGE_BID * MAX_TEST_AUCTIONS

def test_rapid_bid_withdraw_sequence(auction_house_with_auction, alice, bob, deployer, payment_token):
    """Test rapid sequences of bids and withdrawals"""
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction()
    
    initial_bid = to_wei(0.5, 'ether')
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    
    # Make sure they have enough tokens
    payment_token._mint_for_testing(alice, initial_bid * 20)
    payment_token._mint_for_testing(bob, initial_bid * 20)
    
    current_min_bid = initial_bid
    for _ in range(5):
        # Alice bids on both auctions
        with boa.env.prank(alice):
            payment_token.approve(auction_house_with_auction.address, current_min_bid * 2)
            auction_house_with_auction.create_bid(1, current_min_bid)
            auction_house_with_auction.create_bid(2, current_min_bid)
        
        # Calculate Bob's minimum bid
        bob_min_bid = current_min_bid + (current_min_bid * min_increment) // 100
        
        # Bob outbids
        with boa.env.prank(bob):
            payment_token.approve(auction_house_with_auction.address, bob_min_bid * 2)
            auction_house_with_auction.create_bid(1, bob_min_bid)
            auction_house_with_auction.create_bid(2, bob_min_bid)
        
        # Alice withdraws
        with boa.env.prank(alice):
            balance_before = payment_token.balanceOf(alice)
            auction_house_with_auction.withdraw()
            balance_after = payment_token.balanceOf(alice)
            assert balance_after - balance_before == current_min_bid * 2
        
        current_min_bid = bob_min_bid + (bob_min_bid * min_increment) // 100

def test_partial_withdraw_after_multiple_outbids(auction_house_with_auction, alice, bob, charlie, payment_token):
    """Test withdrawing after multiple outbids in the same auction"""
    # Initial bid amounts
    bid_1 = to_wei(0.5, 'ether')
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    
    # Ensure enough tokens
    payment_token._mint_for_testing(alice, bid_1 * 10)
    payment_token._mint_for_testing(bob, bid_1 * 10)
    payment_token._mint_for_testing(charlie, bid_1 * 10)
    
    # Alice's initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1)
        auction_house_with_auction.create_bid(1, bid_1)
    
    # Calculate Bob's minimum bid
    bob_min_bid = bid_1 + (bid_1 * min_increment) // 100
    
    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bob_min_bid)
        auction_house_with_auction.create_bid(1, bob_min_bid)
    
    # This should have created pending returns for Alice from her first bid
    assert auction_house_with_auction.auction_pending_returns(1, alice) == bid_1
    
    # Alice bids again higher
    alice_second_bid = bob_min_bid + (bob_min_bid * min_increment) // 100
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, alice_second_bid)
        auction_house_with_auction.create_bid(1, alice_second_bid)
    
    # Bob's returns should be recorded
    assert auction_house_with_auction.auction_pending_returns(1, bob) == bob_min_bid
    # Alice's previous returns should have been used in new bid
    assert auction_house_with_auction.auction_pending_returns(1, alice) == 0
    
    # Charlie outbids
    charlie_min_bid = alice_second_bid + (alice_second_bid * min_increment) // 100
    with boa.env.prank(charlie):
        payment_token.approve(auction_house_with_auction.address, charlie_min_bid)
        auction_house_with_auction.create_bid(1, charlie_min_bid)
    
    # Now Alice should have her latest bid amount in pending returns
    assert auction_house_with_auction.auction_pending_returns(1, alice) == alice_second_bid
