import pytest
import boa
from dataclasses import dataclass
from typing import Optional

@dataclass
class Auction:
    auction_id: int
    amount: int
    start_time: int
    end_time: int
    bidder: str
    settled: bool
    ipfs_hash: str

@pytest.fixture(scope="function")
def deployer():
    return boa.env.generate_address()

@pytest.fixture(scope="function")
def ipfs_hash():
    return "QmX7L1eLwg9vZ4VBWwHx5KPByYdqhMDDWBJkV8oNJPpqbN"

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
            100,  # reserve_price (100 wei)
            5,    # min_bid_increment_percentage (5%)
            3600, # duration (1 hour)
            proceeds_receiver,
            95,   # proceeds_receiver_split_percentage
            payment_token
        )

@pytest.fixture(scope="function")
def auction_house_with_auction(auction_house, deployer, ipfs_hash):
    """Deploy and unpause the auction house"""
    with boa.env.prank(deployer):
        auction_house.unpause()
        auction_house.create_new_auction(ipfs_hash)  # Create first auction
    return auction_house
