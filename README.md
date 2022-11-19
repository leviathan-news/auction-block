# Leviathan Auction House
![image](https://github.com/user-attachments/assets/de0c8fbb-cf0f-4e82-97cf-7fee9917adc4)

A robust Vypric suite for conducting token auctions with multiple payment options and automated market making functionality.

## Overview

The [Leviathan News](https://leviathannews.xyz/) Auction Block is a decentralized auction platform that enables:
- Single-price English auctions with configurable parameters
- Upgradable modular directory to support future auction types
- Multi-token support via integrated [Curve](https://github.com/curvefi/) trading

## Architecture

To be deployed onto Fraxtal for deploymnet with [SQUID](https://fraxscan.com/token/0x6e58089d8e8f664823d26454f49a5a0f2ff697fe) as the payment token.

### [AuctionDirectory.vy](contracts/AuctionDirectory.vy)

* Central registry for provisioning/disabling all auction contracts and zaps
* Unified delegated bidding interface for users
* Flexible token support management through zap contracts

### [AuctionHouse.vy](contracts/AuctionHouse.vy)

* Reference implementation of English auction mechanics
* Configurable parameters for reserve price, duration, etc.
* Support for auction and bid metadata via IPFS

### [AuctionZap.vy](contracts/AuctionZap.vy)

* Curve AMM integration for token swaps
* Slippage protection
* Safe estimation for bid amounts

## Auction Flow

1. Owner creates auction in Auction House with customizable parameters:
   - Time buffer
   - Reserve price
   - Minimum bid increment
   - Duration

2. Bidders interact with Directory:
   - Place bids in primary token or alternate tokens (provisioned via Zap)
   - Optionally attach IPFS hash to bid with metadata
   - Withdraw failed bids

3. Auction completion:
   - Automatic extension if bid near end
   - Settlement optionally mints NFT to winner
   - Fee distribution

## Security Model

### Access Control

- Two-step ownership transfers
- Granular delegation system
- Clear separation between admin and user functions

### Token Safety

- Tokens always collected before swaps/bids
- Slippage protection on all AMM interactions
- No WETH/ETH held in any contracts

### Emergency Controls

- Pausable functionality at multiple levels
- Auction nullification capability
- Protected withdrawal system

## Development Setup

Deployments artifacts are stored in the [/deployment](/deployment) directory.  Test contracts available on Arbitrum Sepolia to facilitate mock token trading via the [Curve Lite](https://github.com/curvefi/curve-core) deployment.

Test interaction with live auctions via the most current test builds of the UI, available in private repository or demo builds:

- [Web Frontend](https://auction.leviathannews.xyz/auction) *Coming to [@leviathan-news/auction-ui](https://github.com/leviathan-news/auction-ui)*
- [Telegram](https://t.me/AuctionBlockDevChat) *Coming to [@leviathan-news/auction-bot](https://github.com/leviathan-news/auction-bot) h/t [@johnnyonline](https://github.com/johnnyonline)*

### Prerequisites

- Python 3.13 recommended
- [Vyper](https://docs.vyperlang.org/en/stable/installing-vyper.html) 0.4.0
- [Titanoboa](https://titanoboa.readthedocs.io/) 0.2.5

### Environment Setup

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: .\venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Code Quality

Vyper linting is handled using [`mamushi`](https://github.com/benber86/mamushi).  Test and deployment script linting rquires [`black`](https://github.com/psf/black), [`isort`](https://github.com/PyCQA/isort), and [`flake8`](https://github.com/PyCQA/flake8).

## Testing Guide

The project includes comprehensive test suites:

1. Standard tests:
```bash
pytest
```

2. Fork-mode tests (requires Alchemy API key):
```bash
pytest tests/fork --fork
pytest tests/hypothesis --fork
```

3. Coverage reporting:
```bash
pytest --cov=contracts --cov-branch tests/
coverage html
```

View the report in `htmlcov/index.html`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.  Contributions welcomed:

1. Fork the repository
2. Create your feature branch
3. Commit changes with tests
4. Push to your branch
5. Open a Pull Request

## Acknowledgments

Built with:
- [Vyper](https://github.com/vyperlang/) - Smart contract language
- [Boa](https://github.com/vyperlang/titanoboa) - Testing framework
- [Hypothesis](https://hypothesis.works/) - Property-based testing
- [Snekmate](https://github.com/pcaversaccio/snekmate) - NFT and ownable/pausable functions
- [Wen Llama](https://github.com/wen-llama/thellamas) - Forked from the inspirational auctions
