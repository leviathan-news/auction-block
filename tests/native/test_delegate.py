import pytest
import boa


@pytest.fixture(scope="function")
def admin():
    """Admin wallet that will be authorized to bid on behalf of others"""
    return boa.env.generate_address()

def test_set_delegated_bidder(auction_house, deployer, admin, alice):
    """Test setting and removing delegated bidder permissions"""
    # Non-owner cannot set delegated bidder
    with boa.env.prank(alice):
        with boa.reverts("Caller is not the owner"):
            auction_house.set_delegated_bidder(admin, True)
    
    # Owner can set delegated bidder
    with boa.env.prank(deployer):
        auction_house.set_delegated_bidder(admin, True)
    
    assert auction_house.delegated_bidders(admin) == True
    
    # Owner can revoke delegated bidder
    with boa.env.prank(deployer):
        auction_house.set_delegated_bidder(admin, False)
    
    assert auction_house.delegated_bidders(admin) == False


def test_delegated_bid(auction_house_with_auction, admin, alice, payment_token, default_reserve_price):
    """Test bidding on behalf of another user"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Set admin as delegated bidder
    with boa.env.prank(house.owner()):
        house.set_delegated_bidder(admin, True)
    
    # Alice approves contract to spend her tokens
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 2)
    
    # Admin creates bid on behalf of Alice
    with boa.env.prank(admin):
        house.create_bid(auction_id, default_reserve_price, alice)
    
    # Verify bid was recorded for Alice
    auction = house.auction_list(auction_id)
    assert auction[4] == alice, "Bid should be recorded under Alice's address"
    assert payment_token.balanceOf(house.address) == default_reserve_price, "Tokens should be transferred from Alice"


def test_unauthorized_delegated_bid(auction_house_with_auction, admin, alice, bob, payment_token, default_reserve_price):
    """Test that unauthorized addresses cannot bid on behalf of others"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Alice approves contract to spend her tokens
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 2)
    
    # Bob (unauthorized) attempts to bid on behalf of Alice
    with boa.env.prank(bob):
        with boa.reverts("Not authorized to bid on behalf"):
            house.create_bid(auction_id, default_reserve_price, alice)


def test_delegated_bid_with_pending_returns(
    auction_house_with_auction, 
    admin, 
    alice, 
    bob, 
    payment_token,
    default_reserve_price
):
    """Test delegated bidding when the user has pending returns"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Set admin as delegated bidder
    with boa.env.prank(house.owner()):
        house.set_delegated_bidder(admin, True)
    
    # Alice approves and makes initial bid
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 3)
        house.create_bid(auction_id, default_reserve_price)
    
    # Bob outbids Alice
    next_bid = default_reserve_price + (default_reserve_price * house.min_bid_increment_percentage() // 100)
    with boa.env.prank(bob):
        payment_token.approve(house.address, next_bid * 2)
        house.create_bid(auction_id, next_bid)
    
    # Verify Alice has pending returns
    assert house.pending_returns(alice) == default_reserve_price
    
    # Admin bids on behalf of Alice using her pending returns plus additional tokens
    final_bid = next_bid + (next_bid * house.min_bid_increment_percentage() // 100)
    with boa.env.prank(admin):
        house.create_bid(auction_id, final_bid, alice)
    
    auction = house.auction_list(auction_id)
    assert auction[4] == alice, "Bid should be recorded under Alice's address"
    assert house.pending_returns(alice) == 0, "Pending returns should be used for new bid"


def test_delegated_bid_chaining(
    auction_house_with_auction, 
    admin, 
    alice, 
    bob, 
    payment_token,
    default_reserve_price
):
    """Test multiple delegated bids in sequence"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Set admin as delegated bidder
    with boa.env.prank(house.owner()):
        house.set_delegated_bidder(admin, True)
    
    # Both users approve spending
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 3)
    with boa.env.prank(bob):
        payment_token.approve(house.address, default_reserve_price * 3)
    
    # Admin bids alternately for Alice and Bob
    with boa.env.prank(admin):
        house.create_bid(auction_id, default_reserve_price, alice)
        
    auction = house.auction_list(auction_id)
    assert auction[4] == alice
    
    next_bid = default_reserve_price + (default_reserve_price * house.min_bid_increment_percentage() // 100)
    with boa.env.prank(admin):
        house.create_bid(auction_id, next_bid, bob)
        
    auction = house.auction_list(auction_id)
    assert auction[4] == bob
    assert house.pending_returns(alice) == default_reserve_price


def test_delegated_bid_after_revocation(
    auction_house_with_auction, 
    admin, 
    alice, 
    payment_token,
    default_reserve_price
):
    """Test that revoked delegated bidders cannot bid on behalf of others"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Set and then revoke admin as delegated bidder
    with boa.env.prank(house.owner()):
        house.set_delegated_bidder(admin, True)
        house.set_delegated_bidder(admin, False)
    
    # Alice approves contract to spend her tokens
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 2)
    
    # Admin attempts to bid on behalf of Alice after revocation
    with boa.env.prank(admin):
        with boa.reverts("Not authorized to bid on behalf"):
            house.create_bid(auction_id, default_reserve_price, alice)


def test_delegated_bid_withdrawal(
    auction_house_with_auction, 
    admin, 
    alice, 
    bob, 
    payment_token,
    default_reserve_price
):
    """Test that users can withdraw their funds after delegated bids"""
    house = auction_house_with_auction
    auction_id = house.auction_id()
    
    # Set admin as delegated bidder
    with boa.env.prank(house.owner()):
        house.set_delegated_bidder(admin, True)
    
    # Alice approves spending
    with boa.env.prank(alice):
        payment_token.approve(house.address, default_reserve_price * 3)
    
    # Admin bids on behalf of Alice
    with boa.env.prank(admin):
        house.create_bid(auction_id, default_reserve_price, alice)
    
    # Bob outbids
    next_bid = default_reserve_price + (default_reserve_price * house.min_bid_increment_percentage() // 100)
    with boa.env.prank(bob):
        payment_token.approve(house.address, next_bid * 2)
        house.create_bid(auction_id, next_bid)
    
    # Verify Alice can withdraw her outbid amount
    assert house.pending_returns(alice) == default_reserve_price
    
    initial_balance = payment_token.balanceOf(alice)
    with boa.env.prank(alice):
        house.withdraw()
    
    assert payment_token.balanceOf(alice) == initial_balance + default_reserve_price
    assert house.pending_returns(alice) == 0
