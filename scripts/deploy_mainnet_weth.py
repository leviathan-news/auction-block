import os
import sys
from pathlib import Path

import boa
from dotenv import load_dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.config import (
    NETWORK_CONFIGS,
    Network,
    get_constructor_arguments,
    load_keystore,
    save_deployment_info,
    verify_contracts,
)

load_dotenv()

# Configuration
FORK = True  # Set to True to test with mainnet fork
DEPLOY = True  # Set to False to skip deployment
SAVE = False
NETWORK = Network.MAINNET  # Use Network.ARB_SEPOLIA for Arbitrum Sepolia

# Pool addresses (will be used to fetch token addresses)
TRICRV_ADDRS = {
    Network.MAINNET: "0x4eBdF703948ddCEA3B11f675B4D1Fba9d2414A14",
    Network.ARB_SEPOLIA: "0x7ECbDb01E0EA708e5D8f0E07D555a6B61D506A22",
}

# Curve TriCRV pool structure: coin(0) = crvUSD, coin(1) = WETH, coin(2) = CRV
CRVUSD_TRICRV_INDICES = [0, 1]
CRV_TRICRV_INDICES = [2, 1]

# NFT parameters
NFT_NAME = "Leviathan Auction NFT"
NFT_SYMBOL = "SQUID"
NFT_BASE_URI = "https://api.leviathannews.xyz/api/v1/metadata/1/"
NFT_EIP712_NAME = "Leviathan Auction"
NFT_EIP712_VERSION = "1"

# Contract deployment configuration
# Constructor args will be populated after addresses are fetched from pool
CONTRACT_CONFIG = {
    "house": {"file": "AuctionHouse"},
    "directory": {"file": "AuctionDirectory"},
    "nft": {"file": "AuctionNFT"},
    "zap1": {"file": "zaps/AuctionZapTriCRV"},
    "zap2": {"file": "zaps/AuctionZapTriCRV"},
    "oracle": {"file": "AuctionOracleCrvUSD"},
}


def get_token_addresses_from_pool(tricrv_address: str):
    """
    Fetch token addresses from the TriCRV pool.
    Returns dict with 'crvUSD', 'WETH', 'CRV' addresses.
    """
    # Load pool interface
    pool_abi = boa.load_abi("contracts/interfaces/CurveTwoCrypto.json")
    pool = pool_abi.at(tricrv_address)

    # Fetch addresses from pool
    crvusd_addr = pool.coins(0)
    weth_addr = pool.coins(1)
    crv_addr = pool.coins(2)

    return {
        "crvUSD": crvusd_addr,
        "WETH": weth_addr,
        "CRV": crv_addr,
    }


def populate_contract_config(fee_receiver, weth_addr, crvusd_addr, crv_addr, tricrv_addr):
    """Populate CONTRACT_CONFIG with actual constructor argument values"""
    CONTRACT_CONFIG["house"]["constructor_args"] = (weth_addr, fee_receiver)
    CONTRACT_CONFIG["directory"]["constructor_args"] = (weth_addr,)
    CONTRACT_CONFIG["nft"]["constructor_args"] = (
        NFT_NAME,
        NFT_SYMBOL,
        NFT_BASE_URI,
        NFT_EIP712_NAME,
        NFT_EIP712_VERSION,
    )
    CONTRACT_CONFIG["zap1"]["constructor_args"] = (
        weth_addr,
        crvusd_addr,
        tricrv_addr,
        CRVUSD_TRICRV_INDICES,
    )
    CONTRACT_CONFIG["zap2"]["constructor_args"] = (
        weth_addr,
        crv_addr,
        tricrv_addr,
        CRV_TRICRV_INDICES,
    )
    CONTRACT_CONFIG["oracle"]["constructor_args"] = (tricrv_addr,)


def get_contract_deployments():
    """
    Generate contract deployment configuration from CONTRACT_CONFIG.
    Returns list (contract_path, contract_name, contract_type, deploy_args, constructor_args_tuple)
    """
    deployments = []

    for contract_key, config in CONTRACT_CONFIG.items():
        contract_file = config["file"]
        contract_path = f"contracts/{contract_file}.vy"

        # Extract base filename for contract name (remove subdirectory)
        base_filename = Path(contract_file).name

        # Get constructor args (already populated)
        args_tuple = config["constructor_args"]

        deployments.append(
            (
                contract_path,
                base_filename,  # Use base filename as contract name
                contract_key,
                args_tuple,  # Direct args tuple for deployment
                (contract_key, *args_tuple),  # Prepend key for get_constructor_arguments
            )
        )

    return deployments


# Setup environment
network_config = NETWORK_CONFIGS[NETWORK]

# Only ALCHEMY_KEY is read from environment variables
api_key = os.getenv("ALCHEMY_KEY")
if network_config.requires_api_key and not api_key:
    raise ValueError("ALCHEMY_KEY environment variable is required for mainnet")
rpc_url = network_config.get_rpc_url(api_key)

# Setup account and fee receiver
if FORK:
    print(f"Forking {NETWORK.value} at {rpc_url}")
    boa.fork(rpc_url)
    print(f"Fork EOA: {boa.env.eoa}")
    fee_receiver = boa.env.eoa
else:
    try:
        acct = load_keystore("scripts/keystore.json")
        boa.set_network_env(rpc_url)
        boa.env.add_account(acct)
        print(f"Deploying to {NETWORK.value} with account: {acct.address}")
        fee_receiver = acct.address
    except Exception as e:
        raise ValueError(f"Could not load keystore: {e}")

if DEPLOY:
    print("\n" + "=" * 80)
    print(f"DEPLOYING WETH AUCTION SYSTEM ON {NETWORK.value}")
    print("=" * 80)

    # Get TriCRV pool address for this network
    tricrv_addr = TRICRV_ADDRS.get(NETWORK)
    if not tricrv_addr:
        raise ValueError(f"No TriCRV pool address configured for {NETWORK.value}")

    print(f"\nTriCRV Pool Address: {tricrv_addr}")

    # Fetch token addresses from pool
    print("\nFetching token addresses from TriCRV pool...")
    token_addresses = get_token_addresses_from_pool(tricrv_addr)

    WETH_ADDR = token_addresses["WETH"]
    CRVUSD_ADDR = token_addresses["crvUSD"]
    CRV_ADDR = token_addresses["CRV"]

    print(f"  crvUSD: {CRVUSD_ADDR}")
    print(f"  WETH: {WETH_ADDR}")
    print(f"  CRV: {CRV_ADDR}")

    # Populate contract config with actual constructor args
    populate_contract_config(fee_receiver, WETH_ADDR, CRVUSD_ADDR, CRV_ADDR, tricrv_addr)

    # Get contract deployments configuration
    contract_deployments = get_contract_deployments()

    # Load contract partials (deduplicate by path)
    contract_partials = {}
    deployed_contracts = []
    contract_instances = {}

    for (
        contract_path,
        contract_name,
        contract_type,
        deploy_args,
        constructor_args_tuple,
    ) in contract_deployments:
        if contract_path not in contract_partials:
            contract_partials[contract_path] = boa.load_partial(contract_path)

    # Deploy contracts
    print("\nDeploying contracts...")
    for i, (
        contract_path,
        contract_name,
        contract_type,
        deploy_args,
        constructor_args_tuple,
    ) in enumerate(contract_deployments, 1):
        partial = contract_partials[contract_path]

        print(f"\n{i}. Deploying {contract_name}...")
        deployed = partial.deploy(*deploy_args)
        print(f"   ✓ {contract_name} deployed at: {deployed.address}")

        deployed_contracts.append(
            {
                "name": contract_name,
                "path": contract_path,
                "type": contract_type,
                "instance": deployed,
                "constructor_args_tuple": constructor_args_tuple,
            }
        )
        contract_instances[contract_name] = deployed

    # Extract instances for easier access (by contract key from CONTRACT_CONFIG)
    house = contract_instances["AuctionHouse"]
    directory = contract_instances["AuctionDirectory"]
    nft = contract_instances["AuctionNFT"]
    oracle = contract_instances["AuctionOracleCrvUSD"]

    # Get zap instances (they use the same contract file but different deployments)
    zap_instances = [
        info["instance"] for info in deployed_contracts if info["type"] in ["zap1", "zap2"]
    ]
    zap1 = zap_instances[0]  # crvUSD → WETH
    zap2 = zap_instances[1]  # CRV → WETH

    # Configure contracts
    print("\n7. Configuring contracts...")
    house.set_approved_directory(directory.address)
    print("   ✓ Set directory in AuctionHouse")

    directory.register_auction_contract(house)
    directory.add_token_support(CRVUSD_ADDR, zap1)
    directory.add_token_support(CRV_ADDR, zap2)
    directory.set_payment_token_oracle(oracle)
    directory.set_nft(nft.address)
    print("   ✓ Registered house, added crvUSD zap, set oracle, and set NFT in Directory")

    zap1.set_approved_directory(directory.address)
    print("   ✓ Set directory in CRVUSD Zap")

    zap2.set_approved_directory(directory.address)
    print("   ✓ Set directory in CRV Zap")

    print("\n" + "=" * 80)
    print("DEPLOYMENT SUMMARY")
    print("=" * 80)
    print(f"AuctionHouse: {house.address}")
    print(f"AuctionDirectory: {directory.address}")
    print(f"AuctionNFT: {nft.address}")
    print(f"AuctionZap1: {zap1.address} (crvUSD → WETH)")
    print(f"AuctionZap2: {zap2.address} (CRV → WETH)")
    print(f"AuctionOracleCrvUSD: {oracle.address}")
    print(f"Fee Receiver: {fee_receiver}")
    print(f"WETH: {WETH_ADDR}")
    print(f"crvUSD: {CRVUSD_ADDR}")
    print(f"CRV: {CRV_ADDR}")
    print(f"TriCRV Pool: {tricrv_addr}")

    # Generate constructor arguments and save deployment info
    print("\n" + "=" * 80)
    print("CONSTRUCTOR ARGUMENTS FOR VERIFICATION")
    print("=" * 80)

    deployment_params = {
        "fork": FORK,
        "network": NETWORK.value,
        "weth_address": WETH_ADDR,
        "crvusd_address": CRVUSD_ADDR,
        "crv_address": CRV_ADDR,
        "tricrv_address": tricrv_addr,
        "tricrv_eth_indices": CRVUSD_TRICRV_INDICES,
        "tricrv_crv_indices": CRV_TRICRV_INDICES,
        "fee_receiver": fee_receiver,
    }

    if SAVE:
        print("\n" + "=" * 80)
        print("SAVING DEPLOYMENT ARTIFACTS")
        print("=" * 80)

    # Generate constructor args and save for each contract
    for contract_info in deployed_contracts:
        constructor_args = get_constructor_arguments(*contract_info["constructor_args_tuple"])

        # Extract filename from path (e.g., "contracts/AuctionHouse.vy" -> "AuctionHouse")
        contract_filename = Path(contract_info["path"]).stem

        print(f"\n{contract_info['name']} constructor args: {constructor_args}")

        save_deployment_info(
            network=NETWORK.value,
            contract_address=contract_info["instance"].address,
            constructor_args=constructor_args,
            contract_instance=contract_info["instance"],
            deployment_params=deployment_params,
            contract_filename=contract_filename,
            save=SAVE,
        )

    print("\n" + "=" * 80)
    print("DEPLOYMENT COMPLETE!")
    print("=" * 80)
    gas_used = boa.env.get_gas_used()
    print(f"Gas used: {gas_used}")

    if FORK:
        # Gas cost calculations (assuming 1 gwei gas price, ETH = $3500)
        GAS_PRICE_GWEI = 1
        ETH_PRICE_USD = 3500

        gas_cost_wei = gas_used * GAS_PRICE_GWEI * 10**9
        gas_cost_eth = gas_cost_wei / 10**18
        gas_cost_usd = gas_cost_eth * ETH_PRICE_USD

        print("\n" + "=" * 80)
        print("GAS COST ANALYSIS")
        print("=" * 80)
        print(f"Gas Price: {GAS_PRICE_GWEI} gwei")
        eth_price_formatted = format(ETH_PRICE_USD, ",.2f")
        print(f"ETH Price: ${eth_price_formatted}")
        gas_used_formatted = format(gas_used, ",")
        print(f"\nTotal Gas Used: {gas_used_formatted}")
        cost_eth_formatted = format(gas_cost_eth, ".6f")
        print(f"Cost in ETH: {cost_eth_formatted} ETH")
        cost_usd_formatted = format(gas_cost_usd, ".2f")
        print(f"Cost in USD: ${cost_usd_formatted}")
    else:
        # Verify Contracts
        etherscan_api_key = os.getenv("ETHERSCAN_TOKEN")
        # Chain IDs: 1 = Mainnet, 421614 = Arbitrum Sepolia
        chain_ids = {
            Network.MAINNET: 1,
            Network.ARB_SEPOLIA: 421614,
        }
        chain_id = chain_ids.get(NETWORK, 1)

        if etherscan_api_key:
            results = verify_contracts(
                contracts=[info["instance"] for info in deployed_contracts],
                chain_id=chain_id,
                etherscan_api_key=etherscan_api_key,
                continue_on_error=True,  # Don't fail deployment if verification fails
            )
            if results["failed"]:
                print("\n⚠️  Some contracts failed verification.")
                print("   You can retry verification later using:")
                print(f"   python scripts/verify_deployment.py <deployment_yaml_file> {chain_id}")

else:
    print("DEPLOY mode is False. Set DEPLOY=True at top of script to deploy contracts.")
