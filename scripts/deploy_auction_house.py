import os, boa
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3
from hexbytes import HexBytes
from eth_abi import encode

FORK = False
DEPLOY = True

def get_constructor_arguments(time_buffer, reserve_price, min_bid_increment_percentage, 
                            duration, proceeds_receiver, proceeds_receiver_split_percentage, 
                            payment_token):
    """Encode constructor arguments for contract verification"""
    w3 = Web3()
    
    # Convert addresses to checksum format
    proceeds_receiver = w3.to_checksum_address(proceeds_receiver)
    payment_token = w3.to_checksum_address(payment_token)
    
    # Prepare the argument types and values
    types = ['uint256', 'uint256', 'uint256', 'uint256', 'address', 'uint256', 'address']
    values = [
        time_buffer,
        reserve_price,
        min_bid_increment_percentage,
        duration,
        proceeds_receiver,
        proceeds_receiver_split_percentage,
        payment_token
    ]
    
    try:
        # Use eth_abi.encode directly
        encoded = encode(types, values)
        return '0x' + encoded.hex()
    except Exception as e:
        print(f"Encoding error: {str(e)}")
        print("Arguments:", values)
        print("Types:", types)
        return None


load_dotenv()

if FORK:
    RPC_URL = f"https://arb-mainnet.g.alchemy.com/v2/{os.getenv('ALCHEMY_KEY')}"
    boa.fork(RPC_URL)

else:
    acct = Account.from_key(os.getenv("ADMIN_PRIVATE_KEY"))
    boa.set_network_env("https://ethereum-sepolia-rpc.publicnode.com")
    boa.env.add_account(acct)


time_buffer = 300
reserve_price = int(0.2 * 10**18)
min_bid_increment_percentage = 2
duration = 1 * 60 * 60
proceeds_receiver = boa.env.eoa
proceeds_receiver_split_percentage = 100


test_token = boa.load_partial("contracts/test/ERC20.vy")
auction_house = boa.load_partial("contracts/AuctionBlock.vy")

token = "0x899CC89C0A094709CEbBB4AA8C3c2744B75B17Cd"

if DEPLOY:
    #token = test_token.deploy("Test Squid", "SQUID", 18)
    house = auction_house.deploy(
        time_buffer, reserve_price, min_bid_increment_percentage, duration, boa.env.eoa, 100, token
    )

    house.unpause()
    house.create_new_auction()
    print(house.current_auctions())
    print("\nDeployment Info:")
    print(f"Contract Address: {house.address}")

constructor_args = get_constructor_arguments(
    time_buffer,
    reserve_price,
    min_bid_increment_percentage,
    duration,
    proceeds_receiver,
    proceeds_receiver_split_percentage,
    token
)

print(f"Constructor Arguments Bytecode: {constructor_args}")

