from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
import boa
from web3 import Web3


@dataclass
class ContractDefinition:
    name: str  # Contract name (e.g., "AuctionBlock")
    file_path: str  # Path to contract file
    constructor_types: List[str]  # Constructor parameter types
    deployment_order: int  # Order in which contracts should be deployed
    state_getters: List[str] = field(default_factory=list)  # List of state functions to call
    post_deploy_hooks: List[Callable] = field(
        default_factory=list
    )  # Functions to run after deployment


CONTRACTS = {
    "auction_house": ContractDefinition(
        name="AuctionBlock",
        file_path="contracts/AuctionBlock.vy",
        constructor_types=[
            "uint256",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "uint256",
        ],
        deployment_order=1,
        state_getters=["owner", "paused", "auction_id"],
    ),
    "directory": ContractDefinition(
        name="AuctionDirectory",
        file_path="contracts/AuctionDirectory.vy",
        constructor_types=["address"],
        deployment_order=2,
        state_getters=["owner", "paused"],
    ),
    "nft": ContractDefinition(
        name="erc721",
        file_path="contracts/erc721.vy",
        constructor_types=["string"] * 5,
        deployment_order=3,
    ),
    "trader": ContractDefinition(
        name="AuctionTrade",
        file_path="contracts/AuctionTrade.vy",
        constructor_types=["address", "address", "address", "uint256[2]"],
        deployment_order=4,
    ),
}
