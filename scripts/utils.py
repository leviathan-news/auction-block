import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from eth_abi import encode
from web3 import Web3

from contracts import CONTRACTS


def encode_constructor_args(types: List[str], values: List[Any]) -> str:
    w3 = Web3()
    processed_values = [
        w3.to_checksum_address(val) if isinstance(val, str) and val.startswith("0x") else val
        for val in values
    ]

    try:
        encoded = encode(types, processed_values)
        return "0x" + encoded.hex()
    except Exception as e:
        print(f"Encoding error: {str(e)}")
        print("Arguments:", values)
        print("Types:", types)
        return None


def get_vyper_bytecode(contract_path: str) -> Optional[dict]:
    try:
        result = subprocess.run(
            ["vyper", "-f", "solc_json", contract_path], capture_output=True, text=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting Vyper bytecode: {e}")
        return None


def save_deployment_info(
    deployments: Dict[str, Dict[str, Any]], network: str, is_fork: bool = False
):
    """Save all deployment information to YAML"""
    base_dir = Path("deployment")
    network_dir = network.lower() + ("-fork" if is_fork else "")
    chain_dir = base_dir / network_dir
    artifacts_dir = base_dir / "artifacts"

    # Create directories
    for dir_path in [chain_dir, artifacts_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")

    # Create a single deployment record for all contracts
    deployment_record = {
        "network": network,
        "fork": is_fork,
        "deployment_timestamp": datetime.now().isoformat(),
        "contracts": {},
    }

    # Process each deployment
    for contract_id, deployment_data in deployments.items():
        contract_def = CONTRACTS[contract_id]
        contract_addr = deployment_data["address"]

        # Save Vyper output
        addr_prefix = contract_addr[:6].lower()
        artifact_filename = f"{date_str}_{contract_def.name}_{addr_prefix}_vyper_output.json"

        vyper_output = get_vyper_bytecode(contract_def.file_path)
        if vyper_output:
            with open(artifacts_dir / artifact_filename, "w") as f:
                json.dump(vyper_output, f, indent=2)

        # Add to deployment record
        deployment_record["contracts"][contract_id] = {
            "name": contract_def.name,
            "address": contract_addr,
            "constructor_arguments": deployment_data.get("constructor_args"),
            "deployment_parameters": deployment_data.get("params", {}),
            "contract_state": deployment_data.get("state", {}),
            "artifacts": {
                "vyper_output": f"artifacts/{artifact_filename}" if vyper_output else None
            },
        }

    # Save complete deployment record
    filename = f"{date_str}_deployment.yaml"
    with open(chain_dir / filename, "w") as f:
        yaml.dump(deployment_record, f, default_flow_style=False, sort_keys=False)

    print(f"\nDeployment info saved to: {chain_dir / filename}")
