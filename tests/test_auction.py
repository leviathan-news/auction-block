import pytest
import boa

def test_initial_state(auction_house, deployer, proceeds_receiver):
    """Test the initial state of the auction house after deployment"""
    assert auction_house.owner() == deployer
    assert auction_house.time_buffer() == 100
    assert auction_house.reserve_price() == 100
    assert auction_house.min_bid_increment_percentage() == 5
    assert auction_house.duration() == 3600
    assert auction_house.paused() == True
    assert auction_house.proceeds_receiver() == proceeds_receiver
    assert auction_house.proceeds_receiver_split_percentage() == 95
    assert auction_house.auction_id() == 0

def test_create_auction(auction_house, deployer):
    """Test auction creation and initial auction state"""
    # Need to create an auction first since it's not automatically created
    with boa.env.prank(deployer):
        auction_house.unpause()
        auction_house.create_new_auction()
   
    auction_id = auction_house.auction_id()
    auction = auction_house.auction_list(auction_id) 
    # Access tuple values by index based on struct definition order
    assert auction[0] == 1  # auction_id
    assert auction[1] == 0  # amount
    assert auction[2] > 0   # start_time
    assert auction[3] == auction[2] + auction_house.duration()  # end_time
    assert auction[4] == "0x0000000000000000000000000000000000000000"  # bidder
    assert auction[5] == False  # settled

def test_create_bid(auction_house_with_auction, alice):
    """Test basic bid creation"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Print initial state
    print(f"Initial auction state: {house.auction_list(auction_id)}")
    print(f"Alice address: {alice}")
    
    # Test low bid rejection
    with boa.env.prank(alice), boa.reverts("Must send at least reservePrice"):
        house.create_bid(auction_id, 50, value=50)
    
    # Make valid bid
    with boa.env.prank(alice):
        tx = house.create_bid(auction_id, 100, value=100)
    
    # Print post-bid state
    auction = house.auction_list(auction_id)
    print(f"Post-bid auction state: {auction}")
    
    assert auction[4] == alice, f"Expected bidder to be {alice}, got {auction[4]}"
    assert auction[1] == 100, f"Expected amount to be 100, got {auction[1]}"


def test_outbid(auction_house_with_auction, alice, bob):
    """Test outbidding functionality"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Print initial state
    print(f"Initial auction state: {house.auction_list(auction_id)}")
    
    # First bid
    with boa.env.prank(alice):
        house.create_bid(auction_id, 100, value=100)
    
    first_bid_state = house.auction_list(auction_id)
    print(f"After first bid: {first_bid_state}")
    
    # Calculate minimum next bid
    min_next_bid = 100 + (100 * house.min_bid_increment_percentage() // 100)
    print(f"Minimum next bid required: {min_next_bid}")
    
    # Try insufficient bid
    with boa.env.prank(bob), boa.reverts():
        house.create_bid(auction_id, 101, value=101)
    
    # Make successful outbid
    with boa.env.prank(bob):
        house.create_bid(auction_id, min_next_bid, value=min_next_bid)
    
    # Final state checks
    auction = house.auction_list(auction_id)
    print(f"Final auction state: {auction}")
    print(f"Pending returns for alice: {house.pending_returns(alice)}")
    
    assert auction[4] == bob, f"Expected bidder to be {bob}, got {auction[4]}"
    assert auction[1] == min_next_bid, f"Expected amount to be {min_next_bid}, got {auction[1]}"
    assert house.pending_returns(alice) == 100, "Expected alice to have her bid returned"


