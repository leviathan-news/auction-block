import os, boa
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3
from hexbytes import HexBytes
from eth_abi import encode

FORK = False
DEPLOY = True
#NETWORK = "ARB-SEPOLIA"
NETWORK = 'SEPOLIA'

if NETWORK == 'ARB-SEPOLIA':
    RPC = "https://sepolia-rollup.arbitrum.io/rpc"
else:
    RPC = "https://ethereum-sepolia-rpc.publicnode.com"

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
    types = ["uint256", "uint256", "uint256", "uint256", "address", "uint256", "address"]
    values = [
        time_buffer,
        reserve_price,
        min_bid_increment_percentage,
        duration,
        proceeds_receiver,
        proceeds_receiver_split_percentage,
        payment_token,
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


load_dotenv()

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

if NETWORK == "SEPOLIA":
    token = "0x899CC89C0A094709CEbBB4AA8C3c2744B75B17Cd"
elif NETWORK == "ARB-SEPOLIA":
    token = "0x9eE77BFB546805fAfeB0a5e0cb150d5f82cDa47D"
    WETH_ADDR = "0x980b62da83eff3d4576c647993b0c1d7faf17c73"
    POOL_ADDR = "0x3ff0c368af361ff01906f75a7750480d1e2d7aa9"

if DEPLOY:
    # token = test_token.deploy("Test Squid", "SQUID", 18)

    house = auction_house.deploy(
        time_buffer, reserve_price, min_bid_increment_percentage, duration, boa.env.eoa, 100, token
    )

    house.unpause()
    house.create_new_auction()
    print(house.current_auctions())
    print("\nDeployment Info:")
    print(f"Contract Address: {house.address}")

    if NETWORK == "ARB-SEPOLIA":
        trader = auction_trade.deploy(token, WETH_ADDR, POOL_ADDR, [0, 1])
        house.add_token_support(WETH_ADDR, trader)
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
    trade_constructor_args = get_trade_constructor_arguments(
        token,
        WETH_ADDR, 
        POOL_ADDR,
        [0, 1]
    )
    print(f"Trade Constructor Arguments Bytecode: {trade_constructor_args}")
except Exception as e:
    print(f"Trade constructor exception: {e}")

