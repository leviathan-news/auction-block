import boa
import pytest

def test_create_auction_without_ipfs(auction_house, deployer):
    """Test creating an auction without an IPFS hash"""
    with boa.env.prank(deployer):
        auction_house.create_new_auction("")

    auction = auction_house.auction_list(1)
    print(f"Auction state: {auction}")
    assert auction[6] == ""  # ipfs_hash
    assert auction[0] == 1  # auction_id
    assert auction[5] == False  # settled

def test_create_auction_with_ipfs(auction_house, deployer):
    """Test creating an auction with an IPFS hash"""
    test_hash = "QmX7L1eLwg9vZ4VBWwHx5KPByYdqhMDDWBJkV8oNJPpqbN"

    with boa.env.prank(deployer):
        auction_house.create_new_auction(test_hash)

    auction = auction_house.auction_list(1)
    print(f"Auction state: {auction}")
    assert auction[6] == test_hash  # ipfs_hash
    assert auction[0] == 1  # auction_id

def test_ipfs_hash_persists_after_bid(
    auction_house, deployer, alice, payment_token, default_reserve_price
):
    """Test that IPFS hash persists after bids are placed"""
    test_hash = "QmX7L1eLwg9vZ4VBWwHx5KPByYdqhMDDWBJkV8oNJPpqbN"
    bid_amount = default_reserve_price

    # Create auction with IPFS hash
    with boa.env.prank(deployer):
        auction_house.create_new_auction(test_hash)

    print(f"Initial auction state: {auction_house.auction_list(1)}")

    # Place a bid
    with boa.env.prank(alice):
        payment_token.approve(auction_house.address, bid_amount)
        auction_house.create_bid(1, bid_amount)

    auction = auction_house.auction_list(1)
    print(f"Post-bid auction state: {auction}")
    assert auction[6] == test_hash  # ipfs_hash
    assert auction[1] == bid_amount  # amount
    assert auction[4] == alice  # bidder

def test_ipfs_hash_persists_after_settlement(
    auction_house, deployer, alice, payment_token, default_reserve_price
):
    """Test that IPFS hash persists after auction settlement"""
    test_hash = "QmX7L1eLwg9vZ4VBWwHx5KPByYdqhMDDWBJkV8oNJPpqbN"
    bid_amount = default_reserve_price

    # Create and bid on auction
    with boa.env.prank(deployer):
        auction_house.create_new_auction(test_hash)

    print(f"Initial auction state: {auction_house.auction_list(1)}")

    with boa.env.prank(alice):
        payment_token.approve(auction_house.address, bid_amount)
        auction_house.create_bid(1, bid_amount)

    print(f"Post-bid auction state: {auction_house.auction_list(1)}")

    # Fast forward past auction end
    initial_auction = auction_house.auction_list(1)
    boa.env.time_travel(initial_auction[3] + 1)  # end_time + 1

    # Settle auction
    with boa.env.prank(deployer):
        auction_house.settle_auction(1)

    auction = auction_house.auction_list(1)
    print(f"Post-settlement auction state: {auction}")
    assert auction[6] == test_hash  # ipfs_hash
    assert auction[5] == True  # settled
    assert auction[4] == alice  # bidder

def test_multiple_auctions_different_ipfs(auction_house, deployer):
    """Test creating multiple auctions with different IPFS hashes"""
    test_hashes = [
        "QmX7L1eLwg9vZ4VBWwHx5KPByYdqhMDDWBJkV8oNJPpqbN",
        "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "",  # One without IPFS hash
    ]

    with boa.env.prank(deployer):
        # Create multiple auctions
        for hash in test_hashes:
            auction_house.create_new_auction(hash)
            print(f"Created auction with hash: {hash}")
            print(f"Auction state: {auction_house.auction_list(auction_house.auction_id())}")
            boa.env.time_travel(100)

    # Verify each auction has correct IPFS hash
    for i, expected_hash in enumerate(test_hashes, 1):
        auction = auction_house.auction_list(i)
        print(f"Auction {i} state: {auction}")
        assert auction[6] == expected_hash  # ipfs_hash

def test_invalid_ipfs_hash_length(auction_house, deployer):
    """Test that oversized IPFS hashes are rejected"""
    too_long_hash = "Q" * 47  # One character too long

    with boa.env.prank(deployer):
        # Should revert due to string length
        with pytest.raises(Exception):
            auction_house.create_new_auction(too_long_hash)
