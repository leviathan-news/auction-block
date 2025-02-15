import os, boa
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3
from hexbytes import HexBytes
from eth_abi import encode
import os
import yaml
import json
import subprocess
from datetime import datetime
from pathlib import Path

load_dotenv()
FORK = False
DEPLOY = True
NETWORK = "ARB-SEPOLIA"
# NETWORK = 'SEPOLIA'
IPFS_HASH = "QmawoBQWko83vCvD6PfDNi1ED9o6amHrKTiae2mEE8NM77"

if NETWORK == "ARB-SEPOLIA":
    RPC = "https://sepolia-rollup.arbitrum.io/rpc"
else:
    RPC = f"https://eth-sepolia.g.alchemy.com/v2/{os.getenv('ALCHEMY_KEY')}"


def get_directory_constructor_arguments(
    payment_token,
):
    w3 = Web3()
    # Convert addresses to checksum format
    payment_token = w3.to_checksum_address(payment_token)

    types = ["address"]
    values = [payment_token]

    try:
        encoded = encode(types, values)
        return "0x" + encoded.hex()
    except Exception as e:
        print(f"Trade encoding error: {str(e)}")
        print("Arguments:", values)
        print("Types:", types)
        return None


def get_trade_constructor_arguments(
    payment_token,
    trading_token,
    pool,
    indices,
):
    w3 = Web3()
    # Convert addresses to checksum format
    payment_token = w3.to_checksum_address(payment_token)
    trading_token = w3.to_checksum_address(trading_token)
    pool = w3.to_checksum_address(pool)

    types = ["address", "address", "address", "uint256[2]"]
    values = [payment_token, trading_token, pool, indices]

    try:
        encoded = encode(types, values)
        return "0x" + encoded.hex()
    except Exception as e:
        print(f"Trade encoding error: {str(e)}")
        print("Arguments:", values)
        print("Types:", types)
        return None


def get_constructor_arguments(
    time_buffer,
    reserve_price,
    min_bid_increment_percentage,
    duration,
    proceeds_receiver,
    proceeds_receiver_split_percentage,
    payment_token,
):
    """Encode constructor arguments for contract verification"""
    w3 = Web3()

    # Convert addresses to checksum format
    proceeds_receiver = w3.to_checksum_address(proceeds_receiver)
    payment_token = w3.to_checksum_address(payment_token)

    # Prepare the argument types and values
    types = ["uint256", "uint256", "uint256", "uint256", "address", "address", "uint256"]
    values = [
        time_buffer,
        reserve_price,
        min_bid_increment_percentage,
        duration,
        payment_token,
        proceeds_receiver,
        proceeds_receiver_split_percentage,
    ]

    try:
        # Use eth_abi.encode directly
        encoded = encode(types, values)
        return "0x" + encoded.hex()
    except Exception as e:
        print(f"Encoding error: {str(e)}")
        print("Arguments:", values)
        print("Types:", types)
        return None


if FORK:
    if NETWORK == "ARB-SEPOLIA":
        RPC_URL = f"https://arb-sepolia.g.alchemy.com/v2/{os.getenv('ALCHEMY_KEY')}"
    elif NETWORK == "SEPOLIA":
        RPC_URL = f"https://arb-mainnet.g.alchemy.com/v2/{os.getenv('ALCHEMY_KEY')}"
    boa.fork(RPC_URL)
    print(boa.env.eoa)

else:
    acct = Account.from_key(os.getenv("ADMIN_PRIVATE_KEY"))
    boa.set_network_env(RPC)
    boa.env.add_account(acct)


time_buffer = 300
reserve_price = int(0.2 * 10**18)
min_bid_increment_percentage = 2
duration = 1 * 60 * 60
proceeds_receiver = boa.env.eoa
proceeds_receiver_split_percentage = 100


test_token = boa.load_partial("contracts/test/ERC20.vy")
auction_house = boa.load_partial("contracts/AuctionBlock.vy")
auction_trade = boa.load_partial("contracts/AuctionTrade.vy")
auction_directory = boa.load_partial("contracts/AuctionDirectory.vy")

if NETWORK == "SEPOLIA":
    token = "0x899CC89C0A094709CEbBB4AA8C3c2744B75B17Cd"
    WETH_ADDR = "0x0000000000000000000000000000000000000000"
    POOL_ADDR = "0x0000000000000000000000000000000000000000"
elif NETWORK == "ARB-SEPOLIA":
    token = "0x9eE77BFB546805fAfeB0a5e0cb150d5f82cDa47D"
    WETH_ADDR = "0x980b62da83eff3d4576c647993b0c1d7faf17c73"
    POOL_ADDR = "0x3ff0c368af361ff01906f75a7750480d1e2d7aa9"

print("Bytecode size:", len(auction_house.compiler_data.bytecode))

if DEPLOY:

    try:
        house = auction_house.deploy(
            time_buffer,
            reserve_price,
            min_bid_increment_percentage,
            duration,
            token,
            boa.env.eoa,
            100,
            # , gas=3000000
        )
        print("Post-deployment gas used:", boa.env.get_gas_used())

    except Exception as e:
        print(f"Deployment failed with error: {str(e)}")
        print(f"Error type: {type(e)}")
        if hasattr(e, "__dict__"):
            print(f"Error attributes: {e.__dict__}")
        assert False
    # house.unpause()
    house.create_new_auction(IPFS_HASH)
    print(house.current_auctions())
    print("\nDeployment Info:")
    print(f"Contract Address: {house.address}")

    directory = auction_directory.deploy(token)
    print(f"Directory: {directory.address}")

    directory.register_auction_contract(house)
    house.set_approved_directory(directory)

    if NETWORK == "ARB-SEPOLIA":
        trader = auction_trade.deploy(token, WETH_ADDR, POOL_ADDR, [0, 1])
        house.add_token_support(WETH_ADDR, trader)
        directory.add_token_support(WETH_ADDR, trader)
        print(f"Trader contract: {trader.address}")
try:
    constructor_args = get_constructor_arguments(
        time_buffer,
        reserve_price,
        min_bid_increment_percentage,
        duration,
        proceeds_receiver,
        proceeds_receiver_split_percentage,
        token,
    )
except Exception as e:
    print(f"Exception {e}")

print(f"Constructor Arguments Bytecode: {constructor_args}")

try:
    trade_constructor_args = get_trade_constructor_arguments(token, WETH_ADDR, POOL_ADDR, [0, 1])
    print(f"Trade Constructor Arguments Bytecode: {trade_constructor_args}")
except Exception as e:
    print(f"Trade constructor exception: {e}")

try:
    directory_constructor_args = get_directory_constructor_arguments(token)
    print(f"Directory Constructor Arguments Bytecode: {directory_constructor_args}")
except Exception as e:
    print("Directory constructor exception: {e}")


def get_vyper_bytecode(contract_name="AuctionBlock"):
    """Get the Vyper compiler output for contract verification"""
    try:
        result = subprocess.run(
            ["vyper", "-f", "solc_json", f"contracts/{contract_name}.vy"],
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting Vyper bytecode: {e}")
        return None


def save_deployment_info(
    network: str,
    contract_address: str,
    constructor_args: str,
    house,  # Contract instance
    deployment_params: dict,
    contract_filename: str,
):
    """Save deployment information to a YAML file with separate artifact storage"""
    # Create directory structure
    base_dir = Path("deployment")
    network_dir = network.lower()
    if deployment_params["fork"] is True:
        network_dir += "-fork"
    chain_dir = base_dir / network_dir

    artifacts_dir = base_dir / "artifacts"

    # Create directories if they don't exist
    for dir_path in [chain_dir, artifacts_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Generate filenames
    date_str = datetime.now().strftime("%Y%m%d")
    addr_prefix = contract_address[:6].lower()
    yaml_filename = f"{date_str}_{addr_prefix}.yaml"
    artifact_filename = f"{date_str}_{contract_filename}_{addr_prefix}_vyper_output.json"

    # Save Vyper output separately
    vyper_output = get_vyper_bytecode(contract_filename)
    if vyper_output:
        artifact_path = artifacts_dir / artifact_filename
        with open(artifact_path, "w") as f:
            json.dump(vyper_output, f, indent=2)

    # Compile deployment data
    deployment_data = {
        "network": network,
        "fork": deployment_params["fork"],
        "contract_filename": contract_filename,
        "contract_address": contract_address,
        "constructor_arguments": constructor_args,
        "deployment_timestamp": datetime.now().isoformat(),
        "deployment_parameters": {
            "time_buffer": deployment_params["time_buffer"],
            "reserve_price": deployment_params["reserve_price"],
            "min_bid_increment_percentage": deployment_params["min_bid_increment_percentage"],
            "duration": deployment_params["duration"],
            "proceeds_receiver": deployment_params["proceeds_receiver"],
            "proceeds_receiver_split_percentage": deployment_params[
                "proceeds_receiver_split_percentage"
            ],
            "payment_token": deployment_params["token"],
        },
        "contract_state": {
            "owner": house.owner(),
            "paused": house.paused(),
            # "current_auction_id": house.auction_id()
        },
        "artifacts": {"vyper_output": f"artifacts/{artifact_filename}" if vyper_output else None},
    }

    # Save to YAML file
    with open(chain_dir / yaml_filename, "w") as f:
        yaml.dump(deployment_data, f, default_flow_style=False, sort_keys=False)

    print(f"\nDeployment info saved to: {chain_dir / yaml_filename}")
    if vyper_output:
        print(f"Vyper output saved to: {artifacts_dir / artifact_filename}")


if DEPLOY:  # and FORK is False:
    deployment_params = {
        "time_buffer": time_buffer,
        "reserve_price": reserve_price,
        "min_bid_increment_percentage": min_bid_increment_percentage,
        "duration": duration,
        "proceeds_receiver": proceeds_receiver,
        "proceeds_receiver_split_percentage": proceeds_receiver_split_percentage,
        "token": token,
        "fork": FORK,
    }

    save_deployment_info(
        network=NETWORK,
        contract_filename="AuctionBlock",
        contract_address=house.address,
        constructor_args=constructor_args,
        house=house,
        deployment_params=deployment_params,
    )

    if NETWORK == "ARB-SEPOLIA":
        sub = "sepolia.arbiscan.io"
    else:
        sub = "sepolia.etherscan.io"
        print(
            f"https://{sub}/verifyContract-vyper-json?a={house.address}&c=vyper%3a0.4.0&lictype=3"
        )

    save_deployment_info(
        network=NETWORK,
        contract_filename="AuctionDirectory",
        contract_address=directory.address,
        constructor_args=constructor_args,
        house=directory,
        deployment_params=deployment_params,
    )
