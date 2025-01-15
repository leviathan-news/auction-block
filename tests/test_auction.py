import pytest
import boa

@pytest.fixture(scope="function")
def deployer():
    return boa.env.generate_address()

@pytest.fixture(scope="function")
def alice(payment_token):
    addr = boa.env.generate_address()
    payment_token._mint_for_testing(addr, 1_000 * 10 ** 18)
    return addr

@pytest.fixture(scope="function")
def bob(payment_token):
    addr = boa.env.generate_address()
    payment_token._mint_for_testing(addr, 1_000 * 10 ** 18)
    return addr

@pytest.fixture(scope="function")
def charlie(payment_token):
    addr = boa.env.generate_address()
    payment_token._mint_for_testing(addr, 1_000 * 10 ** 18)
    return addr

@pytest.fixture(scope="function")
def payment_token():
    token = boa.load_partial('contracts/test/ERC20.vy')
    return token.deploy("Test Token", "TEST", 18)

@pytest.fixture(scope="function")
def proceeds_receiver():
    return boa.env.generate_address()

@pytest.fixture(scope="function")
def auction_house(deployer, proceeds_receiver, payment_token):
    """Deploy the auction house contract with standard test parameters"""
    with boa.env.prank(deployer):
        contract = boa.load_partial('contracts/AuctionBlock.vy')
        return contract.deploy(
            100,  # time_buffer (100 seconds)
            100,  # reserve_price (100 tokens)
            5,    # min_bid_increment_percentage (5%)
            3600, # duration (1 hour)
            proceeds_receiver,
            95,   # proceeds_receiver_split_percentage
            payment_token
        )

@pytest.fixture(scope="function")
def auction_house_with_auction(auction_house, deployer):
    """Deploy and unpause the auction house"""
    with boa.env.prank(deployer):
        auction_house.unpause()
        auction_house.create_new_auction()  # Create first auction
    return auction_house

def test_initial_state(auction_house, deployer, proceeds_receiver, payment_token):
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
    assert auction_house.payment_token() == payment_token.address

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

def test_create_bid(auction_house_with_auction, alice, payment_token):
    """Test basic bid creation"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Print initial state
    print(f"Initial auction state: {house.auction_list(auction_id)}")
    print(f"Alice address: {alice}")
    
    # Test low bid rejection
    with boa.env.prank(alice):
        payment_token.approve(house.address, 50)
        with boa.reverts("Must send at least reservePrice"):
            house.create_bid(auction_id, 50)
    
    # Make valid bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, 100)
        house.create_bid(auction_id, 100)
    
    # Print post-bid state
    auction = house.auction_list(auction_id)
    print(f"Post-bid auction state: {auction}")
    
    assert auction[4] == alice, f"Expected bidder to be {alice}, got {auction[4]}"
    assert auction[1] == 100, f"Expected amount to be 100, got {auction[1]}"
    assert payment_token.balanceOf(house.address) == 100, "Expected house to hold tokens"

def test_outbid(auction_house_with_auction, alice, bob, payment_token):
    """Test outbidding functionality"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Print initial state
    print(f"Initial auction state: {house.auction_list(auction_id)}")
    
    # First bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, 100)
        house.create_bid(auction_id, 100)
    
    first_bid_state = house.auction_list(auction_id)
    print(f"After first bid: {first_bid_state}")
    
    # Calculate minimum next bid
    min_next_bid = 100 + (100 * house.min_bid_increment_percentage() // 100)
    print(f"Minimum next bid required: {min_next_bid}")
    
    # Try insufficient bid
    with boa.env.prank(bob):
        payment_token.approve(house.address, 101)
        with boa.reverts():
            house.create_bid(auction_id, 101)
    
    # Make successful outbid
    with boa.env.prank(bob):
        payment_token.approve(house.address, min_next_bid)
        house.create_bid(auction_id, min_next_bid)
    
    # Final state checks
    auction = house.auction_list(auction_id)
    print(f"Final auction state: {auction}")
    print(f"Pending returns for alice: {house.pending_returns(alice)}")
    
    assert auction[4] == bob, f"Expected bidder to be {bob}, got {auction[4]}"
    assert auction[1] == min_next_bid, f"Expected amount to be {min_next_bid}, got {auction[1]}"
    assert house.pending_returns(alice) == 100, "Expected alice to have her bid in pending returns"
    # Contract should hold both the current bid and any pending returns
    expected_balance = min_next_bid + house.pending_returns(alice)
    assert payment_token.balanceOf(house.address) == expected_balance, f"Expected house to hold {expected_balance} tokens (current bid + pending returns)"
