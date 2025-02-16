import boa
import pytest


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
    payment_token._mint_for_testing(pool, eth_amount)

    return pool


@pytest.fixture
def mock_trader(payment_token, weth, mock_pool, pool_indices):
    """Deploy mock trader that uses mock pool"""
    contract = boa.load_partial("contracts/AuctionTrade.vy")
    trader = contract.deploy(payment_token, weth, mock_pool.address, pool_indices)
    return trader


def test_trading_views(auction_house, payment_token, weth, mock_trader, mock_pool, directory):
    owner = auction_house.owner()
    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
    val = 10**18
    rate = mock_pool.rate() / 10**18
    assert auction_house.safe_get_dx(weth, val) == val / rate


def test_mock_pool_basic(mock_pool, payment_token, pool_indices, weth):
    """Test that our mock pool works as expected"""
    squid_index = pool_indices[1]
    weth_index = pool_indices[0]

    # Basic pool properties
    assert mock_pool.totalSupply() > 0
    assert mock_pool.coins(squid_index) == payment_token.address
    assert mock_pool.coins(weth_index) == weth.address

    # Exchange rate tests
    input_amount = 1 * 10**18  # 1 token
    output_amount = mock_pool.get_dy(0, 1, input_amount)
    assert output_amount == input_amount * 2  # Using our 2x rate


def test_mock_trader_basic(auction_house, mock_trader, payment_token, alice, mock_pool, weth):
    """Test basic trading functionality using mock trader"""
    reserve = auction_house.default_reserve_price()
    expected = mock_trader.get_dy(reserve)

    # Expected exchange rate
    assert expected == reserve * (mock_pool.rate() / 10**18)

    # Test actual exchange
    init_balance = payment_token.balanceOf(alice)

    with boa.env.prank(alice):
        weth.approve(mock_trader.address, 2**256 - 1)
        received = mock_trader.exchange(reserve, expected)

    assert received == expected
    assert payment_token.balanceOf(alice) == init_balance + expected


def test_mock_bid_with_token(auction_house, mock_trader, payment_token, alice, weth, directory):
    """Test bidding using mock trader"""
    owner = auction_house.owner()

    # Setup auction
    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
        auction_id = auction_house.create_new_auction()

    # Calculate bid amounts
    min_bid = auction_house.minimum_total_bid(auction_id)
    expected_payment = mock_trader.get_dy(min_bid)

    # Place bid
    with boa.env.prank(alice):
        weth.approve(auction_house.address, 2**256 - 1)
        auction_house.create_bid_with_token(auction_id, min_bid, weth, expected_payment)

    # Verify auction state
    auction = auction_house.auction_list(auction_id)
    assert auction[4] == alice  # bidder
    assert auction[1] == expected_payment  # amount


def test_mock_bid_slippage_protection(
    auction_house, mock_trader, payment_token, alice, weth, directory
):
    """Test slippage protection with mock trader"""
    owner = auction_house.owner()

    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
        auction_id = auction_house.create_new_auction()

    min_bid = auction_house.minimum_total_bid(auction_id)
    expected_payment = mock_trader.get_dy(min_bid)

    with boa.env.prank(alice):
        weth.approve(auction_house.address, 2**256 - 1)

        # Try with unrealistic min_amount_out
        with boa.reverts("!token_amount"):
            auction_house.create_bid_with_token(
                auction_id,
                min_bid,
                weth,
                expected_payment * 2,  # Requiring double the expected output
            )


def test_mock_unsupported_token(auction_house, payment_token, alice):
    """Test bidding with unsupported token fails"""
    owner = auction_house.owner()

    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    min_bid = auction_house.minimum_total_bid(auction_id)

    with boa.env.prank(alice):
        payment_token.approve(auction_house.address, 2**256 - 1)
        with pytest.raises(Exception):
            auction_house.create_bid_with_token(
                auction_id, min_bid, payment_token, min_bid  # Token not added to supported tokens
            )


def test_trading_views_in_directory(directory, payment_token, weth, mock_trader, mock_pool):
    owner = directory.owner()
    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
    val = 10**18
    rate = mock_pool.rate() / 10**18
    trader_contract = boa.load_partial("contracts/AuctionTrade.vy")
    trader = trader_contract.at(directory.additional_tokens(weth))
    assert trader.get_dy(val) == val * rate
    assert trader.get_dx(val) == val / rate
    assert trader.safe_get_dx(val) == val / rate


@pytest.mark.skip()
def test_mock_bid_with_token_in_directory(
    auction_house, directory, mock_trader, payment_token, alice, weth
):
    """Test bidding using mock trader"""
    owner = directory.owner()

    # Setup auction
    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
        auction_id = auction_house.create_new_auction()

    # Calculate bid amounts
    min_bid = auction_house.minimum_total_bid(auction_id)
    expected_payment = directory.get_dy(weth, min_bid)

    # Place bid
    with boa.env.prank(alice):
        weth.approve(directory.address, 2**256 - 1)
        directory.create_bid_with_token(auction_house, auction_id, min_bid, weth, expected_payment)

    # Verify auction state
    auction = auction_house.auction_list(auction_id)
    assert auction[4] == alice  # bidder
    assert auction[1] == expected_payment  # amount


@pytest.mark.skip()
def test_mock_bid_slippage_protection_in_directory(
    auction_house, directory, mock_trader, payment_token, alice, weth
):
    """Test slippage protection with mock trader"""
    owner = directory.owner()

    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
        auction_id = auction_house.create_new_auction()

    min_bid = auction_house.minimum_total_bid(auction_id)
    expected_payment = directory.get_dy(weth, min_bid)

    with boa.env.prank(alice):
        weth.approve(directory.address, 2**256 - 1)

        # Try with unrealistic min_amount_out
        with boa.reverts("slippage"):
            directory.create_bid_with_token(
                auction_house,
                auction_id,
                min_bid,
                weth,
                expected_payment * 2,  # Requiring double the expected output
            )


@pytest.mark.skip()
def test_mock_unsupported_token_in_directory(directory, auction_house, payment_token, alice):
    """Test bidding with unsupported token fails"""
    owner = directory.owner()

    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    min_bid = auction_house.minimum_total_bid(auction_id)

    with boa.env.prank(alice):
        payment_token.approve(directory.address, 2**256 - 1)
        with boa.reverts("!contract"):
            directory.create_bid_with_token(
                auction_house,
                auction_id,
                min_bid,
                payment_token,  # Token not added to supported tokens
                min_bid,
            )
