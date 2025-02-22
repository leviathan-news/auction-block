import os
from typing import Any, Dict

import boa
from config import NETWORK_CONFIGS, DeploymentConfig, Network
from dotenv import load_dotenv
from eth_account import Account
from utils import encode_constructor_args, save_deployment_info

from contracts import CONTRACTS, ContractDefinition


def main():
    load_dotenv()

    # Configuration
    config = DeploymentConfig(
        network=Network.ARB_SEPOLIA,
        fork_mode=True,
        deploy_mode=True,
        use_external_tokens=True,
        ipfs_hash="QmQgjigqoR9SRj4bUUNrQ71Kg63Musuyik22eHoAG29w1T",
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
        "payment_token": network_config.token_address,
        "fee_receiver": boa.env.eoa,
    }

    deployments["auction_house"] = deploy_contract(CONTRACTS["auction_house"], auction_params)

    # Deploy Directory
    directory_params = {"payment_token": network_config.token_address}
    deployments["directory"] = deploy_contract(CONTRACTS["directory"], directory_params)

    # Deploy NFT
    nft_params = {
        "name": "Test Leviathan NFT",
        "symbol": "SQUID",
        "base_uri": "https://api.leviathannews.xyz/api/v1/image/",
        "name_eip": "name_eip",
        "version_eip": "version_eip",
    }
    deployments["nft"] = deploy_contract(CONTRACTS["nft"], nft_params)

    # Deploy Trader if needed
    if config.use_external_tokens:
        trader_params = {
            "payment_token": network_config.token_address,
            "weth_address": network_config.weth_address,
            "pool_address": network_config.pool_address,
            "indices": [0, 1],
        }
        deployments["trader"] = deploy_contract(CONTRACTS["trader"], trader_params)

    directory = deployments["directory"]["instance"]
    house = deployments["auction_house"]["instance"]

    if config.network == Network.ARB_SEPOLIA:
        # Deploy Price Oracle
        oracle_params = {
            "squid_price": "0x3ff0c368af361ff01906f75a7750480d1e2d7aa9",
            "eth_price": "0xB051Aefce5095f7c3c3cf3e65e2c4EA80EB8Dc4f",
        }
        deployments["oracle"] = deploy_contract(CONTRACTS["oracle"], oracle_params)
        directory.set_payment_token_oracle(deployments["oracle"]["instance"])
        #house.transfer_ownership("0x5245Cf2b253556D88bF6f783a88229648F957942")
    else:
        print(f"Oracle not set up for {config.network} -- skipping")

    # Configure contract relationships
    nft = deployments["nft"]["instance"]

    directory.register_auction_contract(house)
    house.set_approved_directory(directory)

    if config.ipfs_hash:
        house.create_new_auction(config.ipfs_hash)

    # Set NFT contract
    directory.set_nft(nft.address)
    nft.set_minter(directory, True)

    # Configure trading if enabled
    if config.use_external_tokens and "trader" in deployments:
        trader = deployments["trader"]["instance"]
        directory.add_token_support(network_config.weth_address, trader)
        trader.set_approved_directory(directory)

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
    contract_def: ContractDefinition, deployment_params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Deploy a single contract and return its deployment info"""
    args = list(deployment_params.values())
    contract = boa.load_partial(contract_def.file_path)
    constructor_args = encode_constructor_args(contract_def.constructor_types, args)

    instance = contract.deploy(*args)
    print(f"\n{contract_def.name} deployed at: {instance.address}\n")

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
