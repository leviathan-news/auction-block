import boa
import pytest


def test_trading_views(auction_house, payment_token, weth, mock_trader, mock_pool, directory):
    owner = auction_house.owner()
    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
    val = 10**18
    rate = mock_pool.rate() / 10**18
    assert directory.safe_get_dx(weth, val) == val / rate


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


def test_mock_zap_bid_with_token(
    auction_house,
    mock_trader,
    payment_token,
    alice,
    weth,
    directory,
    approval_flags,
    auction_struct,
):
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
        weth.approve(mock_trader.address, 2**256 - 1)
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(mock_trader, approval_flags.BidOnly)
        mock_trader.zap_and_bid(auction_house, auction_id, min_bid, expected_payment)

    # Verify auction state
    auction = auction_house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == alice  # bidder
    assert auction[auction_struct.amount] == expected_payment  # amount


def test_mock_zap_bid_slippage_protection(
    auction_house, mock_trader, payment_token, alice, weth, directory, approval_flags
):
    """Test slippage protection with mock trader"""
    owner = auction_house.owner()

    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
        auction_id = auction_house.create_new_auction()

    min_bid = auction_house.minimum_total_bid(auction_id)
    expected_payment = mock_trader.get_dy(min_bid)

    with boa.env.prank(alice):
        weth.approve(mock_trader.address, 2**256 - 1)
        payment_token.approve(auction_house.address, 2**256 - 1)
        auction_house.set_approved_caller(mock_trader, approval_flags.BidOnly)

        # Try with unrealistic min_amount_out
        with boa.reverts("!token_amount"):
            mock_trader.zap_and_bid(
                auction_house,
                auction_id,
                min_bid,
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
        # XXX
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
    trader_contract = boa.load_partial("contracts/AuctionZap.vy")
    trader = trader_contract.at(directory.supported_token_zaps(weth))
    assert trader.get_dy(val) == val * rate
    assert trader.get_dx(val) == val / rate
    assert trader.safe_get_dx(val) == val / rate


def test_mock_bid_with_token_in_directory(
    auction_house, directory, mock_trader, payment_token, alice, weth, auction_struct
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
    print(f"Alice has {weth.balanceOf(alice)} WETH for {min_bid} and {expected_payment}")
    with boa.env.prank(alice):
        weth.approve(directory.address, 2**256 - 1)
        directory.create_bid_with_token(auction_house, auction_id, min_bid, weth, expected_payment)

    # Verify auction state
    auction = auction_house.auction_list(auction_id)
    assert auction[auction_struct.bidder] == alice
    assert auction[auction_struct.amount] == expected_payment


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
        with boa.reverts("!token_amount"):
            directory.create_bid_with_token(
                auction_house,
                auction_id,
                min_bid,
                weth,
                expected_payment * 2,  # Requiring double the expected output
            )


def test_mock_unsupported_token_in_directory(directory, auction_house, payment_token, alice):
    """Test bidding with unsupported token fails"""
    owner = directory.owner()

    with boa.env.prank(owner):
        auction_id = auction_house.create_new_auction()

    min_bid = auction_house.minimum_total_bid(auction_id)

    with boa.env.prank(alice):
        payment_token.approve(directory.address, 2**256 - 1)
        with boa.reverts("!token"):
            directory.create_bid_with_token(
                auction_house,
                auction_id,
                min_bid,
                payment_token,  # Token not added to supported tokens
                min_bid,
            )


def test_equal_bid_with_token_directory(
    auction_house_with_auction, directory, alice, weth, mock_trader, payment_token
):
    """Test attempting to bid exactly the current amount"""
    owner = directory.owner()
    auction_id = auction_house_with_auction.auction_id()

    # Setup Directory with token support
    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
        weth._mint_for_testing(alice, 10**23)

    # Place initial bid directly
    initial_bid_squid = auction_house_with_auction.default_reserve_price()
    with boa.env.prank(alice):
        payment_token.approve(auction_house_with_auction, initial_bid_squid)
        auction_house_with_auction.create_bid(auction_id, initial_bid_squid)

    # Get current bid as seen by contract
    current_bid = auction_house_with_auction.auction_bid_by_user(auction_id, alice)
    print(f"Current bid: {current_bid}")

    # Try to "increase" bid to exactly same amount
    # Use 0.01 WETH which should be worth something, but not enough
    weth_amount = 10**16  # 0.01 WETH
    expected_output = directory.get_dy(weth, weth_amount)
    print(f"WETH output: {expected_output}")

    # This should fail with the original code
    with boa.env.prank(alice):
        weth.approve(directory, weth_amount)
        with pytest.raises(Exception) as excinfo:
            directory.create_bid_with_token(
                auction_house_with_auction,
                auction_id,
                weth_amount,
                weth,
                current_bid,  # Exactly equal to current bid
            )
        assert "!bid_amount" in str(excinfo.value), "Should fail with !bid_amount"


def test_eth_bid_to_amount(
    auction_house_with_auction,
    directory,
    alice,
    bob,
    weth,
    mock_trader,
    payment_token,
    precision,
    auction_struct,
    auction_params_struct,
):
    owner = directory.owner()
    with boa.env.prank(owner):
        directory.add_token_support(weth, mock_trader)
    house = auction_house_with_auction
    auction_id = house.auction_id()

    with boa.env.prank(alice):
        min_bid = house.minimum_total_bid(auction_id)
        payment_token.approve(directory, 2**256 - 1)
        directory.create_bid(house, auction_id, min_bid)

    with boa.env.prank(bob):
        bob_first_bid = house.minimum_total_bid(auction_id)
        payment_token.approve(directory, 2**256 - 1)
        directory.create_bid(house, auction_id, bob_first_bid)

    with boa.env.prank(alice):
        alice_final_bid = 10 * 10**18
        assert alice_final_bid > house.minimum_total_bid(auction_id)
        directory.create_bid(house, auction_id, alice_final_bid)

    assert house.auction_list(auction_id)[auction_struct.amount] == alice_final_bid
    assert house.auction_list(auction_id)[auction_struct.bidder] == alice

    with boa.env.prank(bob):
        big_bid = 42 * 10**18
        weth.approve(directory, 2**256 - 1)
        current_bid = house.auction_bid_by_user(auction_id, bob)
        assert current_bid == bob_first_bid
        needed_bid = house.minimum_additional_bid_for_user(auction_id, bob)
        pct = (
            house.auction_list(auction_id)[auction_struct.params][
                auction_params_struct.min_bid_increment_percentage
            ]
            / precision
        )
        assert current_bid + needed_bid == alice_final_bid * (1 + pct)

        needed_dy = big_bid - current_bid
        needed_weth = directory.safe_get_dx(weth, needed_dy)

        directory.create_bid_with_token(house, auction_id, needed_weth, weth, big_bid)

        assert house.auction_list(auction_id)[auction_struct.bidder] == bob
        assert house.auction_list(auction_id)[auction_struct.amount] >= big_bid
        assert house.auction_list(auction_id)[auction_struct.amount] < big_bid * 1.02
