import os, boa
from dotenv import load_dotenv
from eth_account import Account

FORK = True
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
duration = 5400

auction_house = boa.load_partial("contracts/AuctionBlock.vy")

house = auction_house.deploy(
    time_buffer, reserve_price, min_bid_increment_percentage, duration, boa.env.eoa, 100
)

house.unpause()
house.create_new_auction()
print(house.current_auctions())
