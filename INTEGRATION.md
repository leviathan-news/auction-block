# Leviathan Auction Bot Integration Guide

A concise guide for integrating with the Leviathan News auction system on Fraxtal.

## Overview

The Leviathan auction system enables decentralized token auctions with multi-token support via Curve AMM integration. Users can bid using SQUID (primary token) or wfrxETH (alternative token) via built-in zap contract.

## Contract Addresses (Fraxtal)

- **Auction House**: [0xd184CF2f60Da3C54eD1fc371a3e04179C41570c6](https://fraxscan.com/address/0xd184CF2f60Da3C54eD1fc371a3e04179C41570c6)
- **Directory**: [0xd94b2a644b6130B0F14B4fA39b85A5fac450849A](https://fraxscan.com/address/0xd94b2a644b6130B0F14B4fA39b85A5fac450849A)
- **SQUID Token**: [0x6e58089d8e8f664823d26454f49a5a0f2ff697fe](https://fraxscan.com/address/0x6e58089d8e8f664823d26454f49a5a0f2ff697fe)
- **wfrxETH Token**: [0xfc00000000000000000000000000000000000006](https://fraxscan.com/address/0xfc00000000000000000000000000000000000006)

## Key Functions

### 1. Get Active Auctions

```
// Get all active auctions across all registered contracts
function active_auctions() external view returns (AuctionInfo[] memory)

struct AuctionInfo {
    address contract_address;
    uint256 auction_id;
}
```

### 2. Get Auction Details

```
// Check if auction is live
function is_auction_live(uint256 auction_id) external view returns (bool)

// Get remaining time in seconds
function auction_remaining_time(uint256 auction_id) external view returns (uint256)

// Get minimum bid amount
function minimum_total_bid(uint256 auction_id) external view returns (uint256)

// Get user's current bid amount
function auction_bid_by_user(uint256 auction_id, address user) external view returns (uint256)
```

### 3. Place Bids

#### Bid with SQUID (Primary Token)

```
// Via Directory (recommended)
function create_bid(
    AuctionHouse auction_contract,
    uint256 auction_id,
    uint256 bid_amount,
    string calldata ipfs_hash,
    address on_behalf_of
) external

// Direct to Auction House
function create_bid(
    uint256 auction_id,
    uint256 bid_amount,
    string calldata ipfs_hash,
    address on_behalf_of
) external
```

#### Bid with wfrxETH (Alternative Token)

```
// Via Directory with token swap
function create_bid_with_token(
    AuctionHouse auction_contract,
    uint256 auction_id,
    uint256 token_amount,
    IERC20 token,
    uint256 min_total_bid,
    string calldata ipfs_hash,
    address on_behalf_of
) external
```

### 4. Withdraw Funds

```
// Withdraw pending returns from outbid auctions
function withdraw(
    AuctionHouse auction_contract,
    uint256 auction_id,
    address on_behalf_of
) external returns (uint256)

// Batch withdraw from multiple auctions
function withdraw_multiple(
    AuctionHouse auction_contract,
    uint256[] calldata auction_ids,
    address on_behalf_of
) external
```

## Integration Examples

### JavaScript/TypeScript (ethers.js)

```typescript
import { ethers } from 'ethers';

const provider = new ethers.JsonRpcProvider('https://rpc.frax.com');
const directory = new ethers.Contract(DIRECTORY_ADDRESS, directoryABI, provider);

// Get active auctions
const activeAuctions = await directory.active_auctions();

// Get auction details
const auctionHouse = new ethers.Contract(auctionAddress, auctionHouseABI, provider);
const isLive = await auctionHouse.is_auction_live(auctionId);
const minBid = await auctionHouse.minimum_total_bid(auctionId);
const remainingTime = await auctionHouse.auction_remaining_time(auctionId);

// Place bid with SQUID
const squidToken = new ethers.Contract(SQUID_ADDRESS, erc20ABI, signer);
await squidToken.approve(DIRECTORY_ADDRESS, bidAmount);
await directory.create_bid(auctionHouseAddress, auctionId, bidAmount, "", userAddress);

// Place bid with wfrxETH
const wfrxETH = new ethers.Contract(WFRXETH_ADDRESS, erc20ABI, signer);
await wfrxETH.approve(DIRECTORY_ADDRESS, tokenAmount);
await directory.create_bid_with_token(
    auctionHouseAddress, 
    auctionId, 
    tokenAmount, 
    WFRXETH_ADDRESS, 
    minTotalBid, 
    "", 
    userAddress
);
```

### Python (web3.py)

```python
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://rpc.frax.com'))

# Get active auctions
active_auctions = directory.functions.active_auctions().call()

# Place bid
squid_token.functions.approve(DIRECTORY_ADDRESS, bid_amount).transact({'from': user_address})
directory.functions.create_bid(
    auction_house_address,
    auction_id,
    bid_amount,
    "",
    user_address
).transact({'from': user_address})
```

## Important Notes

1. **Token Approvals**: Always approve the Directory contract before bidding
2. **Slippage Protection**: When using alternative tokens, set appropriate `min_total_bid` values
3. **Delegated Bidding**: Use `on_behalf_of` parameter for bot/agent integration
4. **Time Buffer**: Auctions automatically extend if bid placed near end time
5. **Pending Returns**: Outbid users can withdraw funds after auction settlement

## Error Handling

Common revert reasons:
- `!contract`: Auction contract not registered
- `!reservePrice`: Bid below reserve price
- `!increment`: Bid doesn't meet minimum increment
- `!token`: Unsupported token for bidding
- `!caller`: Insufficient delegation permissions

## Live Example

See the system in action: [Auction 45 on Leviathan News](https://leviathannews.xyz/auctions/)

## Resources

- **GitHub**: [leviathan-news/auction-block](https://github.com/leviathan-news/auction-block)
- **Documentation**: See README.md for full technical details
- **Test Contracts**: Available on Arbitrum Sepolia for development
