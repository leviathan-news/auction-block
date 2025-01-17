import pytest
import boa
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
import os

# Fork mode configuration
load_dotenv()
FORK_RPC_URI = f"https://arb-sepolia.g.alchemy.com/v2/{os.getenv('ALCHEMY_KEY')}"
TEST_TOKEN_ADDR = '0x9ee77bfb546805fafeb0a5e0cb150d5f82cda47d'
TEST_POOL_ADDR = '0x3ff0c368af361ff01906f75a7750480d1e2d7aa9'
WETH_ADDR = '0x980b62da83eff3d4576c647993b0c1d7faf17c73'

# Default auction parameters
DEFAULT_TIME_BUFFER = 300
DEFAULT_RESERVE_PRICE = int(0.2 * 10**18)
DEFAULT_MIN_BID_INCREMENT = 2
DEFAULT_DURATION = 1 * 60 * 60
DEFAULT_SPLIT_PERCENTAGE = 100


@dataclass
class Auction:
    auction_id: int
    amount: int
    start_time: int
    end_time: int
    bidder: str
    settled: bool
    ipfs_hash: str


@pytest.fixture(scope="session")
def fork_mode(request):
    """Fixture to determine if tests should run against a fork"""
    return request.config.getoption("--fork", default=False)

def pytest_addoption(parser):
    """Add fork option to pytest"""
    parser.addoption("--fork", action="store_true", help="run tests against fork")

@pytest.fixture(scope="session")
def env(fork_mode):
    """Set up the boa environment based on fork mode"""
    if fork_mode:
        boa.fork(FORK_RPC_URI)
    return boa.env

def pytest_configure(config):
    """Add custom markers to pytest"""
    config.addinivalue_line(
        "markers", "fork_only: mark test to run only when --fork is used"
    )

def pytest_runtest_setup(item):
    """Skip fork_only marks when not in fork mode"""
    if "fork_only" in item.keywords and not item.config.getoption("--fork"):
        pytest.skip("test requires fork network")


@pytest.fixture(scope="session")
def deployer():
    return boa.env.generate_address()

@pytest.fixture(scope="session")
def ipfs_hash():
    return "QmX7L1eLwg9vZ4VBWwHx5KPByYdqhMDDWBJkV8oNJPpqbN"

@pytest.fixture(scope="session")
def weth(env, fork_mode):
    """Get WETH contract interface with deposit functionality"""
    if fork_mode:
        weth_contract = boa.load_partial('contracts/test/IWETH.vy')
        return weth_contract.at(WETH_ADDR)
    else:
        return None


@pytest.fixture(scope="session")
def trading_pool(env, fork_mode):
    pool_contract = boa.load_partial('contracts/test/CurveTwoCrypto.vy')
    if fork_mode:
        return pool_contract.at(TEST_POOL_ADDR)
    else:
        pytest.skip("Trading pool test require fork mode")

@pytest.fixture(scope="session")  
def make_user(payment_token, env, fork_mode, weth):
    def _make_user_with_weth(eth_amount: int = 10 * 10**18):  # Default 10 ETH
        addr = boa.env.generate_address()
        # Fund address with ETH
        boa.env.set_balance(addr, eth_amount)
        # Have user deposit ETH for WETH
        with boa.env.prank(addr):
            weth.deposit(value=eth_amount)
        payment_token._mint_for_testing(addr, 1_000 * 10 ** 18)
        return addr

    def _make_user():
        addr = boa.env.generate_address()
        payment_token._mint_for_testing(addr, 1_000 * 10 ** 18)
        return addr

    if fork_mode:
        return _make_user_with_weth
    else:
        return _make_user

@pytest.fixture(scope="session")
def alice(make_user):
    return make_user()

@pytest.fixture(scope="session")
def bob(make_user):
    return make_user()

@pytest.fixture(scope="session")
def charlie(make_user):
    return make_user()

@pytest.fixture(scope="session")
def payment_token(env, fork_mode):
    token = boa.load_partial('contracts/test/ERC20.vy')
    if fork_mode:
        return token.at(TEST_TOKEN_ADDR)
    else:
        return token.deploy("Test Token", "TEST", 18)

@pytest.fixture(scope="session")
def proceeds_receiver():
    return boa.env.generate_address()


@pytest.fixture(scope="session")
def auction_house_contract():
    """Cache the contract bytecode"""
    return boa.load_partial('contracts/AuctionBlock.vy')

@pytest.fixture(autouse=True)
def state_anchor():
    """Automatically anchor state between tests"""
    with boa.env.anchor():
        yield

@pytest.fixture(scope="session")
def base_auction_house(auction_house_contract, deployer, proceeds_receiver, payment_token):
    """Deploy the auction house contract once for the session"""
    with boa.env.prank(deployer):
        return auction_house_contract.deploy(
            100,  # time_buffer
            100, #DEFAULT_RESERVE_PRICE,  # reserve_price
            5,    # min_bid_increment_percentage
            3600, # duration
            proceeds_receiver,
            95,   # proceeds_receiver_split_percentage
            payment_token
        )

@pytest.fixture
def auction_house(base_auction_house):
    """Return the session-scoped contract for each test"""
    return base_auction_house

@pytest.fixture
def auction_house_with_auction(auction_house, deployer, ipfs_hash):
    """Setup auction state using the session-scoped contract"""
    with boa.env.prank(deployer):
        auction_house.unpause()
        auction_house.create_new_auction(ipfs_hash)
    return auction_house


@pytest.fixture(scope="session")
def pool_indices():
    # WETH -> SQUID
    return [0,1]

@pytest.fixture(scope="session")
def weth_trader(payment_token, weth, trading_pool, pool_indices):
    weth_index = pool_indices[0]
    squid_index = pool_indices[1]
    assert trading_pool.coins(squid_index) == payment_token.address
    assert trading_pool.coins(weth_index) == weth.address

    contract = boa.load_partial('contracts/AuctionTrade.vy')
    return contract.deploy(payment_token, weth, trading_pool, [weth_index, squid_index]) 

@pytest.fixture(scope="session")
def auction_house_with_weth(auction_house_with_auction, weth_trader):
    house = auction_house_with_auction
    
    return auction_house_with_auction
