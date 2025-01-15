import pytest
import boa

@pytest.fixture(scope="function")
def deployer():
    return boa.env.generate_address()

@pytest.fixture(scope="function")
def alice():
    addr = boa.env.generate_address()
    boa.env.set_balance(addr, 10 ** 18)
    return addr

@pytest.fixture(scope="function")
def bob():
    addr = boa.env.generate_address()
    boa.env.set_balance(addr, 10 ** 18)
    return addr


@pytest.fixture(scope="function")
def charlie():
    addr = boa.env.generate_address()
    boa.env.set_balance(addr, 10 ** 18)
    return addr


@pytest.fixture(scope="function")
def proceeds_receiver():
    return boa.env.generate_address()

@pytest.fixture(scope="function")
def auction_house(deployer, proceeds_receiver):
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
        )

@pytest.fixture(scope="function")
def auction_house_with_auction(auction_house, deployer):
    """Deploy and unpause the auction house"""
    with boa.env.prank(deployer):
        auction_house.unpause()
        auction_house.create_new_auction()  # Create first auction
    return auction_house


