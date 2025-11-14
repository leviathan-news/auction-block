#!/usr/bin/env python3
"""
Standalone script to verify contracts from deployment YAML files.

Usage:
  # Verify a single contract YAML file:
  python scripts/verify_deployment.py <deployment_yaml_file> [chain_id]

  # Verify all contracts in a timestamp directory:
  python scripts/verify_deployment.py <timestamp_directory> [chain_id]

Examples:
  # Single contract:
  python scripts/verify_deployment.py deployment/arb-sepolia/20251114_1430/House_0x04f7.yaml 421614

  # All contracts in a deployment:
  python scripts/verify_deployment.py deployment/arb-sepolia/20251114_1430 421614
"""

import os
import re
import sys
from pathlib import Path

import boa
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.config import Network, verify_contracts  # noqa: E402

load_dotenv()

# Chain ID mapping
CHAIN_IDS = {
    Network.MAINNET.value: 1,
    Network.ARB_SEPOLIA.value: 421614,
    Network.SEPOLIA.value: 11155111,
    Network.FRAXTAL.value: 252,  # Add if needed
    # Also support lowercase variants
    "MAINNET": 1,
    "ARB-SEPOLIA": 421614,
    "ARB_SEPOLIA": 421614,
    "SEPOLIA": 11155111,
    "FRAXTAL": 252,
}


def extract_address(address_data):
    """Extract address string from various YAML formats"""
    if isinstance(address_data, str):
        # Clean up address - extract only hex address (42 chars: 0x + 40 hex)
        addr_match = re.search(r"(0x[0-9a-fA-F]{40})", address_data)
        if addr_match:
            return addr_match.group(1)
        return address_data  # Return as-is if no match (might be invalid)
    elif isinstance(address_data, dict):
        if "args" in address_data and isinstance(address_data["args"], list):
            addr = address_data["args"][0]
            # Clean up address if it's a string
            if isinstance(addr, str):
                addr_match = re.search(r"(0x[0-9a-fA-F]{40})", addr)
                if addr_match:
                    return addr_match.group(1)
            return addr
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


def load_yaml_safely(yaml_path: Path) -> dict:
    """Load YAML file, handling boa Address objects and other special types"""
    with open(yaml_path, "r") as f:
        lines = f.readlines()

    # Process line by line to handle Python objects
    cleaned_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Handle Address objects: extract the address from args
        if (
            "!!python/object/new:boa.util.abi.Address" in line
            or "tag:yaml.org,2002:python/object/new:boa.util.abi.Address" in line
        ):
            # Extract key from current line (e.g., "contract_address: !!python/...")
            key_match = re.match(r"^(\s*)([^:]+):\s*!!", line)
            if key_match:
                indent = key_match.group(1)
                key = key_match.group(2).strip()
                i += 1  # Skip tag line
                if i < len(lines) and "args:" in lines[i]:
                    i += 1  # Skip "args:" line
                    if i < len(lines):
                        # Extract address from line like "  - '0x...'"
                        # Match only hex address (0x + 40 hex chars = 42 total)
                        addr_match = re.search(r"'0x([0-9a-fA-F]{40})'", lines[i])
                        if addr_match:
                            # Replace the whole Address object with just the address string
                            cleaned_lines.append(f"{indent}{key}: 0x{addr_match.group(1)}\n")
                        i += 1  # Skip address line
                        # Skip state: and its content (including binary data)
                        while i < len(lines):
                            line_stripped = lines[i].strip()
                            # Stop if we hit a new top-level key (same or less indentation)
                            if line_stripped and not line_stripped.startswith("#"):
                                current_indent = len(lines[i]) - len(lines[i].lstrip())
                                if current_indent <= len(indent) and ":" in line_stripped:
                                    break
                            # Skip state, tuple, binary, and canonical_address lines
                            if (
                                line_stripped.startswith("state:")
                                or line_stripped.startswith("-")
                                or line_stripped.startswith("canonical_address:")
                                or line_stripped.startswith("!!")
                            ):
                                i += 1
                            else:
                                break
                        continue

        # Skip Python tuple and binary objects entirely
        if "!!python/tuple" in line or "!!binary" in line:
            i += 1
            # Skip indented lines that are part of this object
            indent_level = len(line) - len(line.lstrip())
            while i < len(lines):
                next_indent = len(lines[i]) - len(lines[i].lstrip())
                if next_indent > indent_level:
                    i += 1
                else:
                    break
            continue

        # Skip lines that are part of state: blocks
        if line.strip().startswith("state:") or (
            line.strip().startswith("-") and i > 0 and "state:" in lines[i - 1]
        ):
            i += 1
            continue

        cleaned_lines.append(line)
        i += 1

    # Join and parse cleaned YAML
    cleaned_content = "".join(cleaned_lines)
    return yaml.safe_load(cleaned_content)


def verify_from_yaml(yaml_path: Path, chain_id: int = None):
    """Verify all contracts from a deployment YAML file"""
    print(f"Loading deployment from: {yaml_path}")

    data = load_yaml_safely(yaml_path)

    # Determine network and fork status
    network = data.get("network", "UNKNOWN")
    is_fork = data.get("fork", False)

    # Infer chain_id from network if not provided
    if chain_id is None:
        chain_id = CHAIN_IDS.get(network.upper(), CHAIN_IDS.get(network, 1))
        print(f"Inferred chain_id: {chain_id} from network: {network}")
    else:
        print(f"Using provided chain_id: {chain_id}")

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


def verify_from_directory(timestamp_dir: Path, chain_id: int = None):
    """Verify all contracts from a timestamp directory"""
    if not timestamp_dir.is_dir():
        raise ValueError(f"{timestamp_dir} is not a directory")

    # Find all YAML files in the directory
    yaml_files = sorted(timestamp_dir.glob("*.yaml"))

    if not yaml_files:
        print(f"No YAML files found in {timestamp_dir}")
        return

    print(f"Found {len(yaml_files)} contract(s) in {timestamp_dir}")
    print("=" * 80)

    all_contracts = []
    all_contract_names = []
    network = None

    # Load all contracts and determine network from first file
    for yaml_file in yaml_files:
        data = load_yaml_safely(yaml_file)

        # Get network from first file if not set
        if network is None:
            network = data.get("network", "UNKNOWN")
            # Infer chain_id from network if not provided
            if chain_id is None:
                chain_id = CHAIN_IDS.get(network.upper(), CHAIN_IDS.get(network, 1))
                print(f"Inferred chain_id: {chain_id} from network: {network}")
            else:
                print(f"Using provided chain_id: {chain_id}")
            print(f"Network: {network}")
            print(f"Fork: {data.get('fork', False)}")
            print()

        if "contract_address" in data:
            try:
                contract = load_single_contract(data, yaml_file)
                all_contracts.append(contract)
                all_contract_names.append(data.get("contract_filename", "Unknown"))
                contract_addr = contract.address if hasattr(contract, "address") else contract
                print(f"  Loaded {all_contract_names[-1]}: {contract_addr}")
            except Exception as e:
                print(f"  ✗ Failed to load {yaml_file.name}: {e}")

    if not all_contracts:
        print("\nNo contracts loaded. Cannot verify.")
        return

    # Get Etherscan API key
    etherscan_api_key = os.getenv("ETHERSCAN_TOKEN") or os.getenv("ETHERSCAN_API_KEY")
    if not etherscan_api_key:
        print("\n⚠️  No ETHERSCAN_TOKEN or ETHERSCAN_API_KEY found in environment")
        print("   Set one of these environment variables to enable verification")
        return

    # Verify all contracts (verify_contracts will print its own header)
    results = verify_contracts(
        contracts=all_contracts,
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
        print(f"  python scripts/verify_deployment.py {timestamp_dir} {chain_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}")
        sys.exit(1)

    # Chain ID is optional - will be inferred from YAML if not provided
    chain_id = int(sys.argv[2]) if len(sys.argv) > 2 else None

    # Check if it's a directory or a file
    if input_path.is_dir():
        verify_from_directory(input_path, chain_id)
    else:
        verify_from_yaml(input_path, chain_id)
