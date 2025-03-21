import os
from dataclasses import dataclass

import boa
import pytest
from dotenv import load_dotenv

# Fork mode configuration
load_dotenv()
FORK_RPC_URI = f"https://arb-sepolia.g.alchemy.com/v2/{os.getenv('ALCHEMY_KEY')}"
TEST_TOKEN_ADDR = "0x9ee77bfb546805fafeb0a5e0cb150d5f82cda47d"
TEST_POOL_ADDR = "0x3ff0c368af361ff01906f75a7750480d1e2d7aa9"
WETH_ADDR = "0x980b62da83eff3d4576c647993b0c1d7faf17c73"

# Default auction parameters
DEFAULT_TIME_BUFFER = 3600  # 1 hour
DEFAULT_RESERVE_PRICE = int(1000 * 10**18)  # 1000 tokens
DEFAULT_MIN_BID_INCREMENT = 5 * 10**8  # 5$
DEFAULT_DURATION = 24 * 3600  # 1 day
DEFAULT_SPLIT_PERCENTAGE = 100 * 10**8  # 100%
DEFAULT_FEE = 5 * 10**8  # 5%
PRECISION = 100 * 10**8


@dataclass
class Auction:
    auction_id: int
    amount: int
    start_time: int
    end_time: int
    bidder: str
    settled: bool
    ipfs_hash: str


# Fixtures for default values
@pytest.fixture(scope="session")
def default_time_buffer():
    return DEFAULT_TIME_BUFFER


@pytest.fixture(scope="session")
def default_reserve_price():
    return DEFAULT_RESERVE_PRICE


@pytest.fixture(scope="session")
def default_min_bid_increment():
    return DEFAULT_MIN_BID_INCREMENT


@pytest.fixture(scope="session")
def default_duration():
    return DEFAULT_DURATION


@pytest.fixture(scope="session")
def default_split_percentage():
    return DEFAULT_SPLIT_PERCENTAGE


@pytest.fixture(scope="session")
def default_fee():
    return DEFAULT_FEE


@pytest.fixture(scope="session")
def precision():
    return PRECISION


@pytest.fixture(scope="session")
def fee_receiver():
    return boa.env.generate_address()


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
    config.addinivalue_line("markers", "fork_only: mark test to run only when --fork is used")


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
        weth_contract = boa.load_partial("contracts/test/IWETH.vy")
        return weth_contract.at(WETH_ADDR)
    else:
        token = boa.load_partial("contracts/test/ERC20.vy")
        return token.deploy("Test WETH", "WETH", 18)


@pytest.fixture(scope="session")
def trading_pool(env, fork_mode):
    pool_contract = boa.load_abi("contracts/interfaces/CurveTwoCrypto.json")
    if fork_mode:
        return pool_contract.at(TEST_POOL_ADDR)
    else:
        pytest.skip("Trading pool test require fork mode")


@pytest.fixture(scope="session")
def user_mint_amount():
    return 1_000_000 * 10**18


@pytest.fixture(scope="session")
def make_user(payment_token, env, fork_mode, weth, user_mint_amount):
    def _make_user_with_weth(eth_amount: int = 10 * 10**18):  # Default 10 ETH
        addr = boa.env.generate_address()
        boa.env.set_balance(addr, eth_amount)
        with boa.env.prank(addr):
            weth.deposit(value=eth_amount)
        payment_token._mint_for_testing(addr, user_mint_amount)
        return addr

    def _make_user():
        addr = boa.env.generate_address()
        payment_token._mint_for_testing(addr, 1_000_000 * 10**18)
        weth._mint_for_testing(addr, user_mint_amount * 10**18)
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
    token = boa.load_partial("contracts/test/ERC20.vy")
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
    return boa.load_partial("contracts/AuctionHouse.vy")


@pytest.fixture(autouse=True)
def state_anchor():
    """Automatically anchor state between tests"""
    with boa.env.anchor():
        yield


@pytest.fixture(scope="session")
def base_auction_house(
    auction_house_contract,
    deployer,
    fee_receiver,
    payment_token,
    default_time_buffer,
    default_reserve_price,
    default_min_bid_increment,
    default_duration,
    default_fee,
):
    with boa.env.prank(deployer):
        return auction_house_contract.deploy(
            payment_token,
            fee_receiver,
        )


@pytest.fixture(scope="session")
def auction_house(base_auction_house):
    """Return the session-scoped contract for each test"""
    return base_auction_house


@pytest.fixture
def auction_house_with_auction(auction_house, deployer, ipfs_hash):
    """Setup auction state using the session-scoped contract"""
    with boa.env.prank(deployer):
        # auction_house.unpause()
        auction_house.create_new_auction(ipfs_hash)
    return auction_house


@pytest.fixture
def auction_house_with_multiple_auctions(auction_house, deployer):
    """Setup multiple auctions"""
    with boa.env.prank(deployer):
        for _ in range(3):
            auction_house.create_new_auction()
    return auction_house


@pytest.fixture(scope="session")
def pool_indices():
    # WETH -> SQUID
    return [0, 1]


# For testing aspects related to trading tokens outside fork mode
@pytest.fixture(scope="session")
def inert_weth_trader():
    return TEST_POOL_ADDR


# A token, but not WETH compatible (ie deposit)
@pytest.fixture(scope="session")
def inert_weth():
    token = boa.load_partial("contracts/test/ERC20.vy")
    return token.deploy("Inert Wrapped Ether", "WETH", 18)


@pytest.fixture(scope="session")
def weth_trader(payment_token, weth, trading_pool, pool_indices, directory, deployer):
    weth_index = pool_indices[0]
    squid_index = pool_indices[1]
    assert trading_pool.coins(squid_index) == payment_token.address
    assert trading_pool.coins(weth_index) == weth.address

    contract = boa.load_partial("contracts/AuctionZap.vy")
    with boa.env.prank(deployer):
        deployment = contract.deploy(payment_token, weth, trading_pool, [weth_index, squid_index])
        deployment.set_approved_directory(directory)
        directory.add_token_support(weth, deployment)
    return deployment


@pytest.fixture(scope="session")
def auction_house_with_weth(auction_house_with_auction, weth_trader):
    return auction_house_with_auction


@pytest.fixture(scope="session")
def approval_flags():
    class ApprovalFlags:
        Nothing = 1
        BidOnly = 2
        WithdrawOnly = 4
        BidAndWithdraw = 8

    return ApprovalFlags


@pytest.fixture(scope="session")
def auction_struct():
    class AuctionFields:
        auction_id = 0
        amount = 1
        bidder = 2
        start_block = 3
        start_time = 4
        end_time = 5
        settled = 6
        ipfs_hash = 7
        params = 8

    return AuctionFields


@pytest.fixture(scope="session")
def auction_params_struct():
    class AuctionParamsFields:
        time_buffer = 0
        reserve_price = 1
        min_bid_increment_percentage = 2
        duration = 3
        instabuy_price = 4
        beneficiary = 5
        hooker = 6

    return AuctionParamsFields


@pytest.fixture(scope="session")
def nft_contract():
    return boa.load_partial("contracts/AuctionNFT.vy")


@pytest.fixture(scope="session")
def base_uri_prefix():
    return "https://leviathannews.xyz/api/v1/image/"


@pytest.fixture(scope="session")
def base_nft(nft_contract, deployer, base_uri_prefix):
    with boa.env.prank(deployer):
        return nft_contract.deploy("Name", "NFT", base_uri_prefix, "name_eip", "version_eip")


@pytest.fixture
def nft(base_nft, deployer, directory):
    """Return the session-scoped contract for each test"""
    with boa.env.prank(deployer):
        base_nft.set_minter(directory, True)
    return base_nft


@pytest.fixture
def zero_address():
    return "0x0000000000000000000000000000000000000000"


@pytest.fixture(scope="session")
def directory(payment_token, auction_house, deployer):
    """
    Deploy the Auction Directory contract.
    """
    contract = boa.load_partial("contracts/AuctionDirectory.vy")
    with boa.env.prank(deployer):
        deployed = contract.deploy(payment_token)
        deployed.register_auction_contract(auction_house)
        auction_house.set_approved_directory(deployed)
    return deployed


@pytest.fixture
def auction_house_dual_bid(
    auction_house_with_auction, payment_token, alice, bob, default_reserve_price, precision
):
    """
    Deploy the Auction Directory contract.
    """
    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(alice):
        payment_token.approve(house, 2**256 - 1)
        house.create_bid(auction_id, default_reserve_price)

    min_increment = house.default_min_bid_increment_percentage()
    bob_bid = default_reserve_price + (default_reserve_price * min_increment // precision)

    with boa.env.prank(bob):
        payment_token.approve(house, 2**256 - 1)
        house.create_bid(auction_id, bob_bid)

    return house


@pytest.fixture
def mock_pool_contract():
    return boa.load_partial("contracts/test/MockPool.vy")


@pytest.fixture
def mock_pool(mock_pool_contract, payment_token, weth, fork_mode):
    pool = mock_pool_contract.deploy()
    pool.set_coin(1, payment_token.address)  # SQUID
    pool.set_coin(0, weth.address)  # WETH
    eth_amount = 1_000 * 10**18

    addr = boa.env.generate_address()
    if fork_mode:
        boa.env.set_balance(addr, eth_amount)
        with boa.env.prank(addr):
            weth.deposit(value=eth_amount)
            weth.transfer(pool, eth_amount)

    else:
        weth._mint_for_testing(pool, eth_amount)
    payment_token._mint_for_testing(pool, 1000 * eth_amount)

    return pool


@pytest.fixture
def mock_trader(payment_token, weth, mock_pool, pool_indices, directory):
    """Deploy mock trader that uses mock pool"""
    contract = boa.load_partial("contracts/AuctionZap.vy")
    trader = contract.deploy(payment_token, weth, mock_pool.address, pool_indices)
    trader.set_approved_directory(directory)
    return trader


@pytest.fixture
def eth_price():
    return 3000


@pytest.fixture
def mock_oracle_pool(eth_price):
    oracle_contract = boa.load_partial("contracts/test/MockOracle.vy")
    return oracle_contract.deploy(eth_price * 10**18)


@pytest.fixture
def mock_oracle(mock_oracle_pool, mock_pool):
    oracle_contract = boa.load_partial("contracts/AuctionOracle.vy")
    return oracle_contract.deploy(mock_pool, mock_oracle_pool)
