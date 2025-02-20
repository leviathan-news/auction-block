from dataclasses import dataclass, field
from typing import Callable, List


@dataclass
class ContractDefinition:
    name: str  # Contract name (e.g., "AuctionHouse")
    file_path: str  # Path to contract file
    constructor_types: List[str]  # Constructor parameter types
    deployment_order: int  # Order in which contracts should be deployed
    state_getters: List[str] = field(default_factory=list)  # List of state functions to call
    post_deploy_hooks: List[Callable] = field(
        default_factory=list
    )  # Functions to run after deployment


CONTRACTS = {
    "auction_house": ContractDefinition(
        name="AuctionHouse",
        file_path="contracts/AuctionHouse.vy",
        constructor_types=[
            "address",
            "address",
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
        name="AuctionNFT",
        file_path="contracts/AuctionNFT.vy",
        constructor_types=["string"] * 5,
        deployment_order=3,
    ),
    "trader": ContractDefinition(
        name="AuctionZap",
        file_path="contracts/AuctionZap.vy",
        constructor_types=["address", "address", "address", "uint256[2]"],
        deployment_order=4,
    ),
    "oracle": ContractDefinition(
        name="AuctionOracle",
        file_path="contracts/AuctionOracle.vy",
        constructor_types=["address", "address"],
        deployment_order=5,
    ),
}
