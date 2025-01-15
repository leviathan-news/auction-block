import pytest
import boa

def test_auction_extension_near_end(auction_house_with_auction, alice, bob):
    """Test auction extension when bid placed near end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, 100, value=100)
    
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[3]
    
    # Move to near end
    time_to_end = initial_end - initial_auction[2] - 10  # 10 seconds before end
    boa.env.time_travel(seconds=int(time_to_end))
    
    # New bid should extend
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(auction_id, 200, value=200)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[3] > initial_end
    #assert final_auction[3] == boa.env.timestamp + auction_house_with_auction.time_buffer()


def test_auction_extension_not_near_end(auction_house_with_auction, alice, bob):
    """Test auction not extended when bid placed well before end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, 100, value=100)
    
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[3]
    
    # Move to middle of auction
    time_to_move = (initial_end - initial_auction[2]) // 2
    boa.env.time_travel(seconds=int(time_to_move))
    
    # New bid should not extend
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(auction_id, 200, value=200)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[3] == initial_end

def test_consecutive_auctions_pending_returns(auction_house_with_auction, alice, bob, deployer):
    """Test using pending returns across multiple auctions"""
    first_auction_id = auction_house_with_auction.auction_id()
    
    # First auction
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(first_auction_id, 100, value=100)
    
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(first_auction_id, 200, value=200)
    
    assert auction_house_with_auction.pending_returns(alice) == 100
    
    # Settle first auction
    boa.env.time_travel(seconds=4000)
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(first_auction_id)
    
    # Use pending returns in next auction
    second_auction_id = auction_house_with_auction.auction_id()
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(second_auction_id, 100, value=0)  # Use pending returns
    
    second_auction = auction_house_with_auction.auction_list(second_auction_id)
    assert second_auction[4] == alice
    assert second_auction[1] == 100
    assert auction_house_with_auction.pending_returns(alice) == 0

def test_bid_validation_wrong_id(auction_house_with_auction, alice):
    """Test bid for non-existent auction fails"""
    wrong_id = auction_house_with_auction.auction_id() + 1
    
    with boa.env.prank(alice), boa.reverts("Invalid auction ID"):
        auction_house_with_auction.create_bid(wrong_id, 100, value=100)

def test_bid_validation_expired(auction_house_with_auction, alice):
    """Test bid after auction end fails"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Move past auction end
    auction = auction_house_with_auction.auction_list(auction_id)
    time_to_end = auction[3] - auction[2] + 1
    boa.env.time_travel(seconds=int(time_to_end))
    
    with boa.env.prank(alice), boa.reverts("Auction expired"):
        auction_house_with_auction.create_bid(auction_id, 100, value=100)

def test_bid_validation_too_low(auction_house_with_auction, alice):
    """Test bid below reserve price fails"""
    auction_id = auction_house_with_auction.auction_id()
    reserve_price = auction_house_with_auction.reserve_price()
    
    with boa.env.prank(alice), boa.reverts("Must send at least reservePrice"):
        auction_house_with_auction.create_bid(auction_id, reserve_price - 1, value=reserve_price - 1)

def test_bid_increment_validation(auction_house_with_auction, alice, bob):
    """Test minimum bid increment enforcement"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    with boa.env.prank(alice):
        auction_house_with_auction.create_bid(auction_id, 100, value=100)
    
    # Try to bid just slightly higher
    with boa.env.prank(bob), boa.reverts("Must send more than last bid by min_bid_increment_percentage amount"):
        auction_house_with_auction.create_bid(auction_id, 101, value=101)
    
    # Calculate minimum valid next bid
    min_increment = (100 * auction_house_with_auction.min_bid_increment_percentage()) // 100
    min_next_bid = 100 + min_increment
    
    # Valid bid at minimum increment
    with boa.env.prank(bob):
        auction_house_with_auction.create_bid(auction_id, min_next_bid, value=min_next_bid)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[4] == bob
    assert final_auction[1] == min_next_bid
