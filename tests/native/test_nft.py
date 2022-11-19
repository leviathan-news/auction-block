import boa


def test_nft_deployed(nft):
    assert nft.name() == "Name"


def test_nft_minter(nft, directory):
    assert nft.is_minter(directory) is True


def test_nft_direct_mint(nft, deployer, zero_address):
    init_supply = nft.totalSupply()
    with boa.env.prank(deployer):
        nft.safe_mint(deployer, zero_address, 1)
    assert nft.totalSupply() == init_supply + 1


def test_mint_works_without_nft(
    auction_house_with_auction,
    alice,
    default_reserve_price,
    deployer,
    nft,
    payment_token,
    zero_address,
    directory,
):
    house = auction_house_with_auction
    auction_id = house.auction_id()
    with boa.env.prank(alice):
        payment_token.approve(house, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    boa.env.time_travel(seconds=house.auction_remaining_time(auction_id) + 1)

    # Alice wins!
    assert nft.balanceOf(alice) == 0
    assert house.auction_list(auction_id)[4] == alice
    assert directory.nft() == zero_address
    with boa.env.prank(deployer):
        house.settle_auction(auction_id)

    assert nft.balanceOf(alice) == 0
    assert nft.totalSupply() == 0


def test_nft_mints_on_complete_auction(
    auction_house_with_auction,
    alice,
    default_reserve_price,
    deployer,
    nft,
    directory,
    payment_token,
    base_uri_prefix,
):
    house = auction_house_with_auction
    with boa.env.prank(deployer):
        directory.set_nft(nft)
        nft.set_minter(directory, True)
    auction_id = house.auction_id()
    with boa.env.prank(alice):
        payment_token.approve(house, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    boa.env.time_travel(seconds=house.auction_remaining_time(auction_id) + 1)

    # Alice wins!
    assert nft.balanceOf(alice) == 0
    assert house.auction_list(auction_id)[4] == alice
    assert directory.nft() == nft.address
    with boa.env.prank(deployer):
        house.settle_auction(auction_id)

    assert nft.balanceOf(alice) == 1
    token_id = nft.tokenOfOwnerByIndex(alice, 0)
    assert token_id == 1
    assert nft.tokenURI(token_id) == f"{base_uri_prefix}{token_id}"
    with boa.reverts("erc721: invalid token ID"):
        nft.ownerOf(0)
    assert nft.ownerOf(1) == alice


def test_nft_id_matches_auction_id(
    auction_house_with_auction,
    alice,
    default_reserve_price,
    deployer,
    nft,
    payment_token,
    directory,
):
    house = auction_house_with_auction
    with boa.env.prank(deployer):
        directory.set_nft(nft)
    auction_id = house.auction_id()
    with boa.env.prank(alice):
        payment_token.approve(house, default_reserve_price)
        house.create_bid(auction_id, default_reserve_price)

    boa.env.time_travel(seconds=house.auction_remaining_time(auction_id) + 1)

    # Alice wins!
    assert nft.balanceOf(alice) == 0
    assert house.auction_list(auction_id)[4] == alice
    assert directory.nft() == nft.address
    with boa.env.prank(deployer):
        house.settle_auction(auction_id)

    assert nft.balanceOf(alice) == 1
    token_id = nft.tokenOfOwnerByIndex(alice, 0)
    assert token_id == auction_id


def test_nft_not_publicly_callable_via_directory(directory, alice, auction_house, nft):
    with boa.env.prank(alice):
        nft_id = directory.mint_nft(alice, 1)
        assert nft_id == 0

        nft_id = directory.mint_nft(alice, 0)
        assert nft_id == 0
    assert nft.balanceOf(alice) == 0


def test_nft_not_zero_indexed(nft, alice, auction_house, deployer):
    house = auction_house
    assert nft.totalSupply() == 0
    assert nft.balanceOf(alice) == 0
    with boa.env.prank(deployer):
        nft.set_minter(alice, True)
    with boa.env.prank(alice):
        nft.safe_mint(alice, house, 0)

    with boa.reverts("erc721: invalid token ID"):
        nft.ownerOf(0)
    assert nft.ownerOf(1) == alice
    assert nft.tokenOfOwnerByIndex(alice, 0) == 1
    assert nft.tokenByIndex(0) == 1
    assert nft.totalSupply() == 1
    assert nft.balanceOf(alice) == 1
    assert nft.auction_to_token(house, 0) == 1


def test_nft_not_publicly_callable(alice, auction_house, nft):
    with boa.env.prank(alice):
        with boa.reverts("erc721: access is denied"):
            nft.safe_mint(alice, auction_house, 1)
