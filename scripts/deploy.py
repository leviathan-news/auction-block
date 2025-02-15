import os
import boa
from dotenv import load_dotenv
from eth_account import Account
from config import DeploymentConfig, Network, NETWORK_CONFIGS
from contracts import CONTRACTS, ContractDefinition
from utils import encode_constructor_args, save_deployment_info
from typing import List, Any, Dict


def main():
    load_dotenv()

    # Configuration
    config = DeploymentConfig(
        network=Network.ARB_SEPOLIA,
        fork_mode=True,
        deploy_mode=True,
        use_external_tokens=True,
        ipfs_hash="QmawoBQWko83vCvD6PfDNi1ED9o6amHrKTiae2mEE8NM77",
        api_key=os.getenv("ALCHEMY_KEY"),
    )

    network_config = NETWORK_CONFIGS[config.network]
    setup_environment(config)

    if not config.deploy_mode:
        print("Dry run mode - no contracts will be deployed")
        return

    deployments = {}

    # Deploy AuctionHouse
    auction_params = {
        "time_buffer": 300,
        "reserve_price": int(0.2 * 10**18),
        "min_bid_increment_percentage": 2,
        "duration": 3600,
        "payment_token": network_config.token_address,
        "fee_receiver": boa.env.eoa,
        "fee": 100,
    }

    deployments["auction_house"] = deploy_contract(
        CONTRACTS["auction_house"], list(auction_params.values()), auction_params
    )

    # Deploy Directory
    directory_params = {"payment_token": network_config.token_address}
    deployments["directory"] = deploy_contract(
        CONTRACTS["directory"], [network_config.token_address], directory_params
    )

    # Deploy NFT
    nft_params = {
        "name": "Test Leviathan NFT",
        "symbol": "SQUID",
        "base_uri": "https://api.leviathannews.xyz/api/v1/image/",
        "name_eip": "name_eip",
        "version_eip": "version_eip",
    }
    deployments["nft"] = deploy_contract(CONTRACTS["nft"], list(nft_params.values()), nft_params)

    # Deploy Trader if needed
    if config.use_external_tokens:
        trader_params = {
            "payment_token": network_config.token_address,
            "weth_address": network_config.weth_address,
            "pool_address": network_config.pool_address,
            "indices": [0, 1],
        }
        deployments["trader"] = deploy_contract(
            CONTRACTS["trader"], list(trader_params.values()), trader_params
        )

    # Configure contract relationships
    house = deployments["auction_house"]["instance"]
    directory = deployments["directory"]["instance"]
    nft = deployments["nft"]["instance"]

    directory.register_auction_contract(house)
    house.set_approved_directory(directory)

    if config.ipfs_hash:
        house.create_new_auction(config.ipfs_hash)

    # Set NFT contract
    directory.set_nft(nft.address)

    # Configure trading if enabled
    if config.use_external_tokens and "trader" in deployments:
        trader = deployments["trader"]["instance"]
        house.add_token_support(network_config.weth_address, trader)
        directory.add_token_support(network_config.weth_address, trader)

    # Save all deployment information
    save_deployment_info(deployments, config.network.value, config.fork_mode)


def setup_environment(config: DeploymentConfig):
    """Setup boa environment based on configuration"""
    network_config = NETWORK_CONFIGS[config.network]
    rpc_url = network_config.get_rpc_url(config.api_key)

    if config.fork_mode:
        boa.fork(rpc_url)
        print(f"Forked network at {boa.env.eoa}")
    else:
        acct = Account.from_key(os.getenv("ADMIN_PRIVATE_KEY"))
        boa.set_network_env(rpc_url)
        boa.env.add_account(acct)


def deploy_contract(
    contract_def: ContractDefinition, args: List[Any], deployment_params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Deploy a single contract and return its deployment info"""
    contract = boa.load_partial(contract_def.file_path)
    constructor_args = encode_constructor_args(contract_def.constructor_types, args)

    instance = contract.deploy(*args)
    print(f"{contract_def.name} deployed at: {instance.address}")

    # Collect contract state if specified
    state = {}
    for getter in contract_def.state_getters:
        try:
            state[getter] = getattr(instance, getter)()
        except Exception as e:
            print(f"Warning: Failed to get {getter} state: {e}")

    return {
        "instance": instance,
        "address": instance.address,
        "constructor_args": constructor_args,
        "params": deployment_params,
        "state": state,
    }


if __name__ == "__main__":
    main()
