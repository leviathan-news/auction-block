import boa
import pytest



@pytest.fixture
def mock_auction_contract_1():
    """
    Deploy a mock auction contract returning [0,1,2] as active auctions.
    """
    contract = """
    # @version 0.4.0

    @external
    @view
    def current_auctions() -> DynArray[uint256, 1000]:
        return [0, 1, 2]
    """
    return boa.loads(contract)


@pytest.fixture
def mock_auction_contract_2():
    """
    Deploy a mock auction contract returning [6,9,20] as active auctions.
    """
    contract = """
    # @version 0.4.0

    @external
    @view
    def current_auctions() -> DynArray[uint256, 1000]:
        return [6, 9, 420, 69420]
    """
    return boa.loads(contract)


def test_active_auctions(directory, mock_auction_contract_1, mock_auction_contract_2):
    """
    Test if active_auctions() correctly maps contract addresses to active auction lists.
    """

    # Register mock auction contracts
    with boa.env.prank(boa.env.eoa):
        directory.register_auction_contract(mock_auction_contract_1)
        directory.register_auction_contract(mock_auction_contract_2)

    # Fetch active auctions
    active_auctions = directory.active_auctions()

    # Ensure both contracts are listed
    assert len(active_auctions) == 7
    assert active_auctions[0][0] == mock_auction_contract_1.address
    assert active_auctions[1][1] == 1

    print("✅ Test passed: active_auctions() correctly returns contract mappings")



def test_bid_through_directory(deployer, alice, directory, auction_house, payment_token, default_reserve_price):
    #house_contract = boa.load_partial("contracts/AuctionBlock.vy")
    #house = house_contract.at(
    house = auction_house
    with boa.env.prank(deployer):
        house.create_new_auction()

    auction_id = house.auction_id()

    print(f"Alice {alice} bids on {auction_id}")
    with boa.env.prank(alice):
        payment_token.approve(house, default_reserve_price)
        directory.create_bid(house.address, auction_id, default_reserve_price)
    
    assert house.auction_list(auction_id)[4] == alice
    pass


@pytest.mark.fork_only
def test_eth_bid_through_directory():
    pass
