import getpass
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import boa
import yaml
from eth_abi import encode
from eth_account import Account
from web3 import Web3


class Network(Enum):
    ARB_SEPOLIA = "ARB-SEPOLIA"
    SEPOLIA = "SEPOLIA"
    FRAXTAL = "FRAXTAL"
    MAINNET = "MAINNET"


@dataclass
class NetworkConfig:
    base_rpc_url: str
    token_address: str
    weth_address: str = ""
    pool_address: str = ""
    eth_pool_address: str = ""
    crvusd_address: str = ""
    fee_receiver: str = ""
    use_external_tokens: bool = False
    requires_api_key: bool = False

    def get_rpc_url(self, api_key: Optional[str] = None) -> str:
        if self.requires_api_key:
            if not api_key:
                raise ValueError(f"API key required for {self.base_rpc_url}")
            return f"{self.base_rpc_url}/{api_key}"
        return self.base_rpc_url


@dataclass
class DeploymentConfig:
    network: Network
    fork_mode: bool = False
    deploy_mode: bool = True
    use_external_tokens: bool = False
    ipfs_hash: str = ""
    fee_receiver: Optional[str] = None
    api_key: Optional[str] = None


NETWORK_CONFIGS = {
    Network.ARB_SEPOLIA: NetworkConfig(
        base_rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
        token_address="0x9eE77BFB546805fAfeB0a5e0cb150d5f82cDa47D",
        weth_address="0x980b62da83eff3d4576c647993b0c1d7faf17c73",
        pool_address="0x3ff0c368af361ff01906f75a7750480d1e2d7aa9",
        use_external_tokens=True,
    ),
    Network.FRAXTAL: NetworkConfig(
        base_rpc_url="https://rpc.frax.com",
        token_address="0x6e58089d8e8f664823d26454f49a5a0f2ff697fe",
        weth_address="0xfc00000000000000000000000000000000000006",
        pool_address="0x277fa53c8a53c880e0625c92c92a62a9f60f3f04",
        eth_pool_address="0xa0d3911349e701a1f49c1ba2dda34b4ce9636569",
        fee_receiver="0xBd4ab1139F2F6361f927b8552C3b97Fe81f0B528",
        use_external_tokens=True,
    ),
    Network.SEPOLIA: NetworkConfig(
        base_rpc_url="https://eth-sepolia.g.alchemy.com/v2",
        token_address="0x899CC89C0A094709CEbBB4AA8C3c2744B75B17Cd",
        requires_api_key=True,
    ),
    Network.MAINNET: NetworkConfig(
        base_rpc_url="https://eth-mainnet.g.alchemy.com/v2",
        token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        weth_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        pool_address="0x4eBdF703948ddCEA3B11f675B4D1Fba9d2414A14",  # Curve TriCRV pool
        crvusd_address="0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E",
        use_external_tokens=True,
        requires_api_key=True,
    ),
}

# Contract constructor argument types
CONTRACT_TYPES = {
    "house": ["address", "address"],
    "directory": ["address"],
    "zap": ["address", "address", "address", "uint256[2]"],
    "oracle": ["address"],
    "nft": ["string", "string", "string", "string", "string"],
}


def get_constructor_arguments(contract_type: str, *values):
    """
    Generic function to encode constructor arguments for any contract type.

    Args:
        contract_type: One of "house", "directory", "zap", "oracle", "nft"
        *values: Constructor argument values (addresses will be checksummed automatically)

    Returns:
        Hex-encoded constructor arguments string, or None on error
    """
    if contract_type not in CONTRACT_TYPES:
        print(f"Unknown contract type: {contract_type}")
        return None

    types = CONTRACT_TYPES[contract_type]
    if len(values) != len(types):
        print(
            f"Argument count mismatch for {contract_type}: expected {len(types)}, got {len(values)}"
        )
        return None

    w3 = Web3()
    processed_values = []
    for i, (value, type_str) in enumerate(zip(values, types)):
        # Checksum addresses
        if type_str == "address":
            processed_values.append(w3.to_checksum_address(value))
        # Arrays pass through as-is
        elif "[" in type_str:
            processed_values.append(value)
        # Everything else (strings, etc.) passes through
        else:
            processed_values.append(value)

    try:
        encoded = encode(types, processed_values)
        return "0x" + encoded.hex()
    except Exception as e:
        print(f"{contract_type.capitalize()} encoding error: {str(e)}")
        return None


def get_vyper_bytecode(contract_name):
    """Get the Vyper compiler output for contract verification"""
    try:
        result = subprocess.run(
            ["vyper", "-f", "solc_json", f"contracts/{contract_name}.vy"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Vyper compilation error for {contract_name}: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error getting Vyper bytecode for {contract_name}: {e}")
        return None


def save_deployment_info(
    network: str,
    contract_address: str,
    constructor_args: str,
    contract_instance,
    deployment_params: dict,
    contract_filename: str,
    save: bool = False,
):
    """
    Save deployment information to a YAML file with separate artifact storage.

    Args:
        network: Network name
        contract_address: Deployed contract address
        constructor_args: Encoded constructor arguments
        contract_instance: Contract instance (unused but kept for compatibility)
        deployment_params: Dictionary of deployment parameters
        contract_filename: Contract filename (without .vy extension)
        save: Whether to save deployment info (default: False)
    """
    if not save:
        return

    # Create directory structure with timestamp subdirectory
    base_dir = Path("deployment")
    network_dir = network.lower()
    if deployment_params.get("fork", False):
        network_dir += "-fork"

    # Use shared deployment timestamp if available, otherwise generate one
    timestamp_str = deployment_params.get("deployment_timestamp") or datetime.now().strftime(
        "%Y%m%d_%H%M"
    )

    # Create timestamped subdirectories
    chain_dir = base_dir / network_dir / timestamp_str
    artifacts_dir = base_dir / "artifacts" / timestamp_str

    # Create directories if they don't exist
    for dir_path in [chain_dir, artifacts_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Generate filenames
    addr_prefix = contract_address[:6].lower()
    # Short contract name (e.g., "AuctionHouse" -> "House")
    contract_short_name = contract_filename.replace("Auction", "")
    yaml_filename = f"{contract_short_name}_{addr_prefix}.yaml"
    artifact_filename = f"{contract_filename}_{addr_prefix}_vyper_output.json"

    # Save Vyper output separately
    vyper_output = get_vyper_bytecode(contract_filename)
    if vyper_output:
        artifact_path = artifacts_dir / artifact_filename
        with open(artifact_path, "w") as f:
            json.dump(vyper_output, f, indent=2)

    # Compile deployment data
    deployment_data = {
        "network": network,
        "fork": deployment_params.get("fork", False),
        "contract_filename": contract_filename,
        "contract_address": contract_address,
        "constructor_arguments": constructor_args,
        "deployment_timestamp": datetime.now().isoformat(),
        "deployment_parameters": deployment_params,
        "artifacts": {
            "vyper_output": (
                f"artifacts/{timestamp_str}/{artifact_filename}" if vyper_output else None
            )
        },
    }

    # Save to YAML file
    with open(chain_dir / yaml_filename, "w") as f:
        yaml.dump(deployment_data, f, default_flow_style=False, sort_keys=False)

    print(f"\nDeployment info saved to: {chain_dir / yaml_filename}")
    if vyper_output:
        print(f"Vyper output saved to: {artifacts_dir / artifact_filename}")


def verify_contracts(
    contracts: list, chain_id: int, etherscan_api_key: str, continue_on_error: bool = True
):
    """
    Verify deployed contracts on Etherscan.

    Args:
        contracts: List of contract instances to verify
        chain_id: Chain ID for the network (1 for mainnet, etc.)
        etherscan_api_key: Etherscan API key for verification
        continue_on_error: If True, continue verifying other contracts even if one fails

    Returns:
        dict: Results with 'success' and 'failed' lists of contract addresses
    """
    results = {"success": [], "failed": []}

    if not etherscan_api_key:
        print("No Etherscan API key provided, skipping verification")
        return results

    etherscan_url = f"https://api.etherscan.io/v2/api?chainid={chain_id}"  # noqa: E231
    boa.set_etherscan(etherscan_url, etherscan_api_key)
    verifier = boa.Etherscan(etherscan_url, etherscan_api_key)

    print("\n" + "=" * 80)
    print("VERIFYING CONTRACTS")
    print("=" * 80)

    for contract in contracts:
        contract.ctor_calldata = b""
        try:
            print(f"Verifying {contract.address}...")
            boa.verify(contract, verifier=verifier)
            print(f"   ✓ Verified {contract.address}")
            results["success"].append(contract.address)
        except Exception as e:
            error_msg = str(e)
            print(f"   ✗ Verification failed for {contract.address}: {error_msg}")
            results["failed"].append({"address": contract.address, "error": error_msg})
            if not continue_on_error:
                print("\nStopping verification due to error (continue_on_error=False)")
                break

    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Successfully verified: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")
    if results["failed"]:
        print("\nFailed contracts:")
        for failure in results["failed"]:
            print(f"- {failure['address']}: {failure['error']}")

    return results


def load_keystore(keystore_path):
    with open(keystore_path, "r") as file:
        keystore_data = json.load(file)
    password = getpass.getpass("Enter keystore password: ")
    acct = Account.from_key(Account.decrypt(keystore_data, password))
    return acct
