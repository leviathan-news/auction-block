import boa


def test_mock_pool_with_oracle_returns_price(mock_oracle_pool, eth_price):
    assert mock_oracle_pool.price_oracle(0) == eth_price * 10**18


def test_mock_oracle_has_eth_price(mock_oracle, eth_price):
    assert mock_oracle.eth_price_usd() == eth_price * 10**18


def test_mock_oracle_has_squid_eth_price(mock_oracle, mock_pool):
    assert mock_oracle.squid_price_eth() == mock_pool.price_oracle()


def test_mock_zap_has_correct_squid_price(mock_oracle, eth_price, mock_pool):
    squid_price_eth = mock_pool.price_oracle()
    assert mock_oracle.price_usd() == squid_price_eth * eth_price


def test_directory_returns_token_price(directory, mock_oracle, eth_price, mock_pool):
    with boa.env.prank(directory.owner()):
        directory.set_payment_token_oracle(mock_oracle)
    assert directory.payment_token_price_usd() == mock_pool.price_oracle() * eth_price
