import pytest
import boa
from eth_utils import to_wei
from typing import Tuple

def unpack_auction(auction_tuple: Tuple) -> dict:
    """Helper to unpack auction data from contract return tuple"""
    return {
        'auction_id': auction_tuple[0],
        'amount': auction_tuple[1],
        'start_time': auction_tuple[2],
        'end_time': auction_tuple[3],
        'bidder': auction_tuple[4],
        'settled': auction_tuple[5],
        'ipfs_hash': auction_tuple[6]
    }

def test_create_multiple_auctions(auction_house_with_auction, deployer, ipfs_hash):
    """Test that multiple auctions can be created and tracked correctly"""
    # Create second and third auctions
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)
        auction_house_with_auction.create_new_auction(ipfs_hash)
    
    # Check current auctions
    active_auctions = auction_house_with_auction.current_auctions()
    assert len(active_auctions) == 3
    assert active_auctions == [1, 2, 3]

def test_separate_auction_states(auction_house_with_auction, alice, bob, deployer, ipfs_hash, payment_token):
    """Test that auctions maintain separate states and bids"""
    # Create second auction
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)
    
    bid_amount_1 = to_wei(0.5, 'ether')
    bid_amount_2 = to_wei(0.6, 'ether')
    
    # Approve and bid from Alice
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_amount_1)
        auction_house_with_auction.create_bid(1, bid_amount_1)
    
    # Approve and bid from Bob
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bid_amount_2)
        auction_house_with_auction.create_bid(2, bid_amount_2)
    
    # Verify separate auction states
    auction_1 = unpack_auction(auction_house_with_auction.auction_list(1))
    auction_2 = unpack_auction(auction_house_with_auction.auction_list(2))
    
    assert auction_1['bidder'] == alice
    assert auction_1['amount'] == bid_amount_1
    assert auction_2['bidder'] == bob
    assert auction_2['amount'] == bid_amount_2

def test_cross_auction_pending_returns(auction_house_with_auction, alice, bob, deployer, ipfs_hash, payment_token):
    """Test complex scenario where a user tries to use pending returns across multiple auctions"""
    # Create second auction
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)
    
    bid_1 = to_wei(0.5, 'ether')
    bid_2 = to_wei(0.6, 'ether')
    
    # Alice bids on auction 1
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1)
        auction_house_with_auction.create_bid(1, bid_1)
    
    # Bob outbids Alice
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bid_2)
        auction_house_with_auction.create_bid(1, bid_2)
    
    # Alice has pending returns
    alice_pending = auction_house_with_auction.pending_returns(alice)
    assert alice_pending == bid_1
    
    # Alice tries to bid on auction 2 using only pending returns
    with boa.env.prank(alice):
        with pytest.raises(Exception):  # Should fail since pending returns require new approval
            auction_house_with_auction.create_bid(2, bid_1)
    
    # Alice properly bids with new approval
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1)
        auction_house_with_auction.create_bid(2, bid_1)

def test_auction_timing_isolation(auction_house_with_auction, alice, bob, deployer, ipfs_hash, payment_token):
    """Test that auction timing extensions are properly isolated"""
    # Create second auction
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)
    
    # Move forward to near end of auctions
    time_buffer = auction_house_with_auction.time_buffer()
    duration = auction_house_with_auction.duration()

    boa.env.time_travel(seconds=duration - time_buffer + 1) 
    
    bid_1 = to_wei(0.5, 'ether')
    
    # Record initial end times
    auction_1_start = unpack_auction(auction_house_with_auction.auction_list(1))
    auction_2_start = unpack_auction(auction_house_with_auction.auction_list(2))
    
    # Place last-minute bid on auction 1
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1)
        auction_house_with_auction.create_bid(1, bid_1)
    
    # Check end times
    auction_1_after = unpack_auction(auction_house_with_auction.auction_list(1))
    auction_2_after = unpack_auction(auction_house_with_auction.auction_list(2))
    
    assert auction_1_after['end_time'] > auction_1_start['end_time']  # Extended
    assert auction_2_after['end_time'] == auction_2_start['end_time']  # Unchanged

def test_concurrent_minimum_bids(auction_house_with_auction, alice, bob, deployer, ipfs_hash, payment_token):
    """Test minimum bid calculations across concurrent auctions"""
    # Create second auction
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)
    
    min_increment = auction_house_with_auction.min_bid_increment_percentage()
    
    bid_1_alice = to_wei(0.5, 'ether')
    bid_2_bob = to_wei(0.6, 'ether')
    
    # Place initial bids
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1_alice)
        auction_house_with_auction.create_bid(1, bid_1_alice)
    
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bid_2_bob)
        auction_house_with_auction.create_bid(2, bid_2_bob)
    
    # Check minimum bids for each auction
    min_bid_1 = auction_house_with_auction.minimum_total_bid(1)
    min_bid_2 = auction_house_with_auction.minimum_total_bid(2)
    
    expected_min_1 = bid_1_alice + (bid_1_alice * min_increment) // 100
    expected_min_2 = bid_2_bob + (bid_2_bob * min_increment) // 100
    
    assert min_bid_1 == expected_min_1
    assert min_bid_2 == expected_min_2


def test_settlement_interaction(auction_house_with_auction, alice, bob, deployer, ipfs_hash, payment_token):
    """Test that settling one auction doesn't affect others"""
    # Create second auction
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)
    
    bid_1 = to_wei(0.5, 'ether')
    bid_2 = to_wei(0.6, 'ether')
    
    # Place bids on both auctions
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1 * 2)
        auction_house_with_auction.create_bid(1, bid_1)
        auction_house_with_auction.create_bid(2, bid_1)
    
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bid_2)
        auction_house_with_auction.create_bid(1, bid_2)
    
    # Time travel past end
    boa.env.time_travel(seconds=3700)
    
    # Settle first auction
    auction_house_with_auction.settle_auction(1)
    
    # Verify second auction unaffected
    auction_2 = unpack_auction(auction_house_with_auction.auction_list(2))
    assert not auction_2['settled']
    assert auction_2['bidder'] == alice
    assert auction_2['amount'] == bid_1

def test_partial_returns_usage(auction_house_with_auction, alice, bob, deployer, ipfs_hash, payment_token):
    """Test that partial returns can only be used in the same auction they came from"""
    # Create second auction
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)

    bid_1 = to_wei(0.5, 'ether')
    bid_2 = to_wei(0.3, 'ether')  # Smaller bid
    large_bid = to_wei(0.8, 'ether')

    # Alice's initial bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1)
        auction_house_with_auction.create_bid(1, bid_1)

    # Bob outbids
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, large_bid)
        auction_house_with_auction.create_bid(1, large_bid)

    # Alice now has pending returns from auction 1
    assert auction_house_with_auction.pending_returns(alice) == bid_1

    # Alice attempts to use returns from auction 1 in auction 2
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_2)
        # This should require full new payment since returns are auction-specific
        auction_house_with_auction.create_bid(2, bid_2)

    # Original returns from auction 1 should remain untouched
    assert auction_house_with_auction.pending_returns(alice) == bid_1

def test_cascading_returns(auction_house_with_auction, alice, bob, charlie, deployer, ipfs_hash, payment_token):
    """Test that returns stay isolated to their originating auctions"""
    # Create additional auctions
    with boa.env.prank(deployer):
        auction_house_with_auction.create_new_auction(ipfs_hash)
        auction_house_with_auction.create_new_auction(ipfs_hash)

    bid_1 = to_wei(0.5, 'ether')
    bid_2 = to_wei(0.6, 'ether')
    bid_3 = to_wei(0.7, 'ether')

    # Alice bids on all three auctions
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_1 * 3)
        auction_house_with_auction.create_bid(1, bid_1)
        auction_house_with_auction.create_bid(2, bid_1)
        auction_house_with_auction.create_bid(3, bid_1)

    # Verify initial state - no returns yet
    assert auction_house_with_auction.pending_returns(alice) == 0

    # Bob outbids on first auction
    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, bid_2)
        auction_house_with_auction.create_bid(1, bid_2)

    # Verify returns from auction 1
    assert auction_house_with_auction.auction_pending_returns(1, alice) == bid_1
    assert auction_house_with_auction.pending_returns(alice) == bid_1

    # Alice attempts higher bid on auction 2
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, bid_2)
        auction_house_with_auction.create_bid(2, bid_2)

    # Should now have returns from auctions 1 and 2
    assert auction_house_with_auction.auction_pending_returns(1, alice) == bid_1  # From Bob's outbid
    assert auction_house_with_auction.auction_pending_returns(2, alice) == bid_1  # From self-outbid
    assert auction_house_with_auction.pending_returns(alice) == bid_1 * 2

    # Charlie outbids on third auction
    with boa.env.prank(charlie):
        payment_token.approve(auction_house_with_auction.address, bid_3)
        auction_house_with_auction.create_bid(3, bid_3)

    # Verify final returns state
    assert auction_house_with_auction.auction_pending_returns(1, alice) == bid_1  # From Bob's outbid
    assert auction_house_with_auction.auction_pending_returns(2, alice) == bid_1  # From self-outbid
    assert auction_house_with_auction.auction_pending_returns(3, alice) == bid_1  # From Charlie's outbid
    assert auction_house_with_auction.pending_returns(alice) == bid_1 * 3  # Total from all auctions

    # Verify auction states
    auction_1 = unpack_auction(auction_house_with_auction.auction_list(1))
    auction_2 = unpack_auction(auction_house_with_auction.auction_list(2))
    auction_3 = unpack_auction(auction_house_with_auction.auction_list(3))

    assert auction_1['bidder'] == bob
    assert auction_2['bidder'] == alice
    assert auction_3['bidder'] == charlie

def test_consecutive_auctions_pending_returns(auction_house_with_auction, alice, bob, deployer, payment_token):
    """Test that pending returns are auction-specific and can't be used across auctions"""
    first_auction_id = auction_house_with_auction.auction_id()

    # First auction
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(first_auction_id, 100)

    with boa.env.prank(bob):
        payment_token.approve(auction_house_with_auction.address, 200)
        auction_house_with_auction.create_bid(first_auction_id, 200)

    # Verify returns from first auction
    assert auction_house_with_auction.auction_pending_returns(first_auction_id, alice) == 100
    assert auction_house_with_auction.pending_returns(alice) == 100

    # Settle first auction
    boa.env.time_travel(seconds=4000)
    with boa.env.prank(deployer):
        auction_house_with_auction.pause()
        auction_house_with_auction.settle_and_create_auction(first_auction_id)

    # Second auction - should NOT be able to use pending returns from first auction
    second_auction_id = auction_house_with_auction.auction_id()

    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction.address, 100)
        auction_house_with_auction.create_bid(second_auction_id, 100)

    second_auction = auction_house_with_auction.auction_list(second_auction_id)
    assert second_auction[4] == alice
    assert second_auction[1] == 100

    # Alice should STILL have her pending returns from first auction
    assert auction_house_with_auction.auction_pending_returns(first_auction_id, alice) == 100
    assert auction_house_with_auction.auction_pending_returns(second_auction_id, alice) == 0
    assert auction_house_with_auction.pending_returns(alice) == 100  # Still has returns from first auction
