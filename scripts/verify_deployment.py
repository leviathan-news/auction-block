#!/usr/bin/env python3
"""
Standalone script to verify contracts from deployment YAML files.

Usage:
    python scripts/verify_deployment.py <deployment_yaml_file> [chain_id]

Example:
    python scripts/verify_deployment.py deployment/mainnet-fork/20251113_0xc6ac.yaml 1
"""

import os
import sys
from pathlib import Path

import boa
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.config import verify_contracts  # noqa: E402

load_dotenv()


def extract_address(address_data):
    """Extract address string from various YAML formats"""
    if isinstance(address_data, str):
        return address_data
    elif isinstance(address_data, dict):
        if "args" in address_data and isinstance(address_data["args"], list):
            return address_data["args"][0]
        elif "canonical_address" in address_data:
            # Try to decode binary address (unlikely but handle it)
            return None
    return None


def load_contract_from_address_and_filename(address: str, contract_filename: str):
    """Load a contract instance given address and filename"""
    # Determine contract path
    contract_filename_clean = contract_filename.replace(".vy", "")

    # Handle zaps in subdirectories
    if "zap" in contract_filename_clean.lower() and "tri" in contract_filename_clean.lower():
        contract_path = "contracts/zaps/AuctionZapTriCRV.vy"
    elif "zap" in contract_filename_clean.lower():
        contract_path = f"contracts/zaps/{contract_filename_clean}.vy"
    else:
        contract_path = f"contracts/{contract_filename_clean}.vy"

    try:
        partial = boa.load_partial(contract_path)
        return partial.at(address)
    except Exception as e:
        print(f"  Warning: Could not load {contract_path}: {e}")
        print(f"  Contract may need to be verified manually at {address}")
        # Return a minimal object with address attribute

        class ContractPlaceholder:
            def __init__(self, addr):
                self.address = addr

        return ContractPlaceholder(address)


def load_single_contract(data: dict, yaml_path: Path):
    """Load a single contract from YAML (newer format)"""
    address_data = data.get("contract_address")
    contract_filename = data.get("contract_filename", "Unknown")

    address = extract_address(address_data)
    if not address:
        raise ValueError(f"Could not extract address from YAML: {address_data}")

    return load_contract_from_address_and_filename(address, contract_filename)


def verify_from_yaml(yaml_path: Path, chain_id: int = 1):
    """Verify all contracts from a deployment YAML file"""
    print(f"Loading deployment from: {yaml_path}")

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # Determine network and fork status
    network = data.get("network", "UNKNOWN")
    is_fork = data.get("fork", False)

    print(f"Network: {network}")
    print(f"Fork: {is_fork}")

    # Setup boa environment
    if is_fork:
        print("Note: This is a fork deployment. Verification may not work correctly.")
        print("Consider using the actual network deployment YAML instead.")

    contracts = []
    contract_names = []

    # Try to load contracts
    if "contract_address" in data:
        # Single contract format (newer)
        try:
            contract = load_single_contract(data, yaml_path)
            contracts.append(contract)
            contract_names.append(data.get("contract_filename", "Contract"))
            contract_addr = contract.address if hasattr(contract, "address") else contract
            print(f"  Loaded {contract_names[-1]}: {contract_addr}")
        except Exception as e:
            print(f"  ✗ Failed to load contract: {e}")
    elif "contracts" in data:
        # Multi-contract format (older)
        for contract_name, contract_data in data["contracts"].items():
            try:
                address_data = contract_data.get("address") or contract_data.get("contract_address")
                address = extract_address(address_data)
                if not address:
                    raise ValueError(f"Could not extract address for {contract_name}")

                contract_filename = contract_data.get("contract_filename") or contract_data.get(
                    "name", contract_name
                )
                contract = load_contract_from_address_and_filename(address, contract_filename)
                contracts.append(contract)
                contract_names.append(contract_name)
                contract_addr = contract.address if hasattr(contract, "address") else contract
                print(f"  Loaded {contract_name}: {contract_addr}")
            except Exception as e:
                print(f"  ✗ Failed to load {contract_name}: {e}")
    else:
        print("  ✗ No contracts found in YAML file")
        print("  Expected 'contract_address' or 'contracts' key")
        return

    if not contracts:
        print("\nNo contracts loaded. Cannot verify.")
        return

    # Get Etherscan API key
    etherscan_api_key = os.getenv("ETHERSCAN_TOKEN") or os.getenv("ETHERSCAN_API_KEY")
    if not etherscan_api_key:
        print("\n⚠️  No ETHERSCAN_TOKEN or ETHERSCAN_API_KEY found in environment")
        print("   Set one of these environment variables to enable verification")
        return

    # Verify contracts
    results = verify_contracts(
        contracts=contracts,
        chain_id=chain_id,
        etherscan_api_key=etherscan_api_key,
        continue_on_error=True,
    )

    # Print summary
    print("\n" + "=" * 80)
    if results["success"]:
        print(f"✓ Successfully verified {len(results['success'])} contract(s)")
    if results["failed"]:
        print(f"✗ Failed to verify {len(results['failed'])} contract(s)")
        print("\nTo retry verification, run this script again or use:")
        print(f"  python scripts/verify_deployment.py {yaml_path} {chain_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    yaml_path = Path(sys.argv[1])
    if not yaml_path.exists():
        print(f"Error: File not found: {yaml_path}")
        sys.exit(1)

    chain_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    verify_from_yaml(yaml_path, chain_id)
