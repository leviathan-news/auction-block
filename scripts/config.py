from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Network(Enum):
    ARB_SEPOLIA = "ARB-SEPOLIA"
    SEPOLIA = "SEPOLIA"
    FRAXTAL = "FRAXTAL"


@dataclass
class NetworkConfig:
    base_rpc_url: str
    token_address: str
    weth_address: str = ""
    pool_address: str = ""
    eth_pool_address: str = ""
    fee_receiver: str = ""
    use_external_tokens: bool = False
    requires_api_key: bool = False

    def get_rpc_url(self, api_key: Optional[str] = None) -> str:
        if self.requires_api_key:
            if not api_key:
                raise ValueError(f"API key required for {self.base_rpc_url}")
            return f"{self.base_rpc_url}/{api_key}"
        return self.base_rpc_url


@dataclass
class DeploymentConfig:
    network: Network
    fork_mode: bool = False
    deploy_mode: bool = True
    use_external_tokens: bool = False
    ipfs_hash: str = ""
    fee_receiver: Optional[str] = None
    api_key: Optional[str] = None


NETWORK_CONFIGS = {
    Network.ARB_SEPOLIA: NetworkConfig(
        base_rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
        token_address="0x9eE77BFB546805fAfeB0a5e0cb150d5f82cDa47D",
        weth_address="0x980b62da83eff3d4576c647993b0c1d7faf17c73",
        pool_address="0x3ff0c368af361ff01906f75a7750480d1e2d7aa9",
        use_external_tokens=True,
    ),
    Network.FRAXTAL: NetworkConfig(
        base_rpc_url="https://rpc.frax.com",
        token_address="0x6e58089d8e8f664823d26454f49a5a0f2ff697fe",
        weth_address="0xfc00000000000000000000000000000000000006",
        pool_address="0x277fa53c8a53c880e0625c92c92a62a9f60f3f04",
        eth_pool_address="0xa0d3911349e701a1f49c1ba2dda34b4ce9636569",
        fee_receiver="0xBd4ab1139F2F6361f927b8552C3b97Fe81f0B528",
        use_external_tokens=True,
    ),
    Network.SEPOLIA: NetworkConfig(
        base_rpc_url="https://eth-sepolia.g.alchemy.com/v2",
        token_address="0x899CC89C0A094709CEbBB4AA8C3c2744B75B17Cd",
        requires_api_key=True,
    ),
}
