import pytest
import boa

def test_auction_extension_near_end(auction_house_with_auction, alice, bob, payment_token, default_reserve_price):
    """Test auction extension when bid placed near end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    bid_amount = default_reserve_price
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)
    
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[3]
    
    # Move to near end
    time_to_end = initial_end - initial_auction[2] - 10  # 10 seconds before end
    boa.env.time_travel(seconds=int(time_to_end))
    
    # Calculate next bid
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    next_bid = bid_amount + (bid_amount * min_increment) // 100
    
    # New bid should extend
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, next_bid)
        auction_house_with_auction.create_bid(auction_id, next_bid)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[3] > initial_end


def test_auction_extension_not_near_end(
    auction_house_with_auction, 
    alice, 
    bob, 
    payment_token,
    default_reserve_price
):
    """Test auction not extended when bid placed well before end"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid
    bid_amount = default_reserve_price
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)
    
    initial_auction = auction_house_with_auction.auction_list(auction_id)
    initial_end = initial_auction[3]
    
    # Move to middle of auction
    time_to_move = (initial_end - initial_auction[2]) // 2
    boa.env.time_travel(seconds=int(time_to_move))
    
    # Calculate next bid
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    next_bid = bid_amount + (bid_amount * min_increment) // 100
    
    # New bid should not extend
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, next_bid)
        auction_house_with_auction.create_bid(auction_id, next_bid)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[3] == initial_end


def test_bid_validation_wrong_id(auction_house_with_auction, alice, payment_token, default_reserve_price):
    """Test bid for non-existent auction fails"""
    wrong_id = auction_house_with_auction.auction_id() + 1
    
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        with boa.reverts("Invalid auction ID"):
            auction_house_with_auction.create_bid(wrong_id, default_reserve_price)


def test_bid_validation_expired(auction_house_with_auction, alice, payment_token, default_reserve_price):
    """Test bid after auction end fails"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Move past auction end
    auction = auction_house_with_auction.auction_list(auction_id)
    time_to_end = auction[3] - auction[2] + 1
    boa.env.time_travel(seconds=int(time_to_end))
    
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, default_reserve_price)
        with boa.reverts("Auction expired"):
            auction_house_with_auction.create_bid(auction_id, default_reserve_price)


def test_bid_validation_too_low(auction_house_with_auction, alice, payment_token, default_reserve_price):
    """Test bid below reserve price fails"""
    auction_id = auction_house_with_auction.auction_id()
    low_bid = default_reserve_price - 1
    
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, low_bid)
        with boa.reverts("Must send at least reservePrice"):
            auction_house_with_auction.create_bid(auction_id, low_bid)


def test_bid_increment_validation(
    auction_house_with_auction, 
    alice, 
    bob, 
    payment_token,
    default_reserve_price
):
    """Test minimum bid increment enforcement"""
    auction_id = auction_house_with_auction.auction_id()
    
    # Initial bid at reserve price
    bid_amount = default_reserve_price
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount)
        auction_house_with_auction.create_bid(auction_id, bid_amount)
    
    # Try to bid just slightly higher
    insufficient_increment = bid_amount + 1
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, insufficient_increment)
        with boa.reverts("Must send more than last bid by min_bid_increment_percentage amount"):
            auction_house_with_auction.create_bid(auction_id, insufficient_increment)
    
    # Calculate minimum valid next bid
    min_increment = (bid_amount * auction_house_with_auction.min_bid_increment_percentage()) // 100
    min_next_bid = bid_amount + min_increment
    
    # Valid bid at minimum increment
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, min_next_bid)
        auction_house_with_auction.create_bid(auction_id, min_next_bid)
    
    final_auction = auction_house_with_auction.auction_list(auction_id)
    assert final_auction[4] == bob
    assert final_auction[1] == min_next_bid
