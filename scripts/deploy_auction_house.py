import os

import boa
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()
acct = Account.from_key(os.getenv("ADMIN_PRIVATE_KEY"))

boa.set_network_env("https://ethereum-sepolia-rpc.publicnode.com")
boa.env.add_account(acct)

time_buffer = 300
reserve_price = int(0.2 * 10**18)
min_bid_increment_percentage = 2
duration = 5400

auction_house = boa.load_partial("contracts/AuctionBlock.vy")

auction_house.deploy(
    time_buffer, reserve_price, min_bid_increment_percentage, duration, boa.env.eoa, 100
)
