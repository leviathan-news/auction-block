# Leviathan Auction House
![image](https://github.com/user-attachments/assets/de0c8fbb-cf0f-4e82-97cf-7fee9917adc4)

A robust smart contract system for conducting token auctions with multiple payment options and automated market making functionality.

## Overview

Leviathan Auction House is a decentralized auction platform that enables:
- Single-price English auctions with configurable parameters
- Upgradable directory to support future auction types
- Multi-token support through integrated AMM trading
- Automated auction extension to prevent sniping
- Flexible bidding permissions and delegation
- Comprehensive fee management
- Safety features including pausability and emergency auction nullification

## Key Features

- Configurable auction parameters (reserve price, duration, bid increments)
- Support for alternate payment tokens through AMM integration
- Anti-sniping mechanism with automatic time extension
- Delegated bidding capabilities
- Fee distribution system
- Emergency controls for auction management
- Comprehensive test coverage

## Core Components

### AuctionDirectory.vy

* Central registry for all auction contracts and zaps
* Unified bidding interface for users
* Token support management through zap contracts
* Permission and delegation system

### AuctionBlock.vy

* Reference implementation of English auction mechanics
* Configurable parameters for reserve price, duration, etc.
* Support for metadata via IPFS
* Fee distribution system

### AuctionZap.vy (Zap Contract)

* Curve AMM integration for token swaps
* Slippage protection
* Safe estimation for bid amounts

## Security Model

### Access Control

- Two-step ownership transfers
- Granular delegation system
- Clear separation between admin and user functions

### Token Safety

- Tokens always collected before swaps/bids
- Slippage protection on all AMM interactions
- Independent balance verification

### Emergency Controls

- Pausable functionality at multiple levels
- Auction nullification capability
- Protected withdrawal system

## Development Setup

### Prerequisites

- Python 3.7+
- [Vyper](https://docs.vyperlang.org/en/stable/installing-vyper.html) 0.4.0
- Node.js and npm (for development tools)

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

3. Configure environment variables:
```bash
cp example.env .env
```

### Code Quality

1. Lint Vyper files:
```bash
mamushi
```

2. Format Python files:
```bash
black .
```

## Architecture

### Auction Flow

1. Owner creates auction with parameters:
   - Time buffer
   - Reserve price
   - Minimum bid increment
   - Duration
   - Payment token
   - Fee configuration

2. Users can:
   - Place bids in primary token
   - Place bids in alternate tokens (auto-converted via AMM)
   - Delegate bidding permissions
   - Withdraw failed bids

3. Auction completion:
   - Automatic extension if bid near end
   - Settlement transfers tokens to winner
   - Fee distribution
   - Optional NFT minting for winners

### Security Features

- Two-step ownership transfers
- Pausable functionality
- Emergency auction nullification
- Slippage protection for token swaps
- Comprehensive access controls

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit changes with tests
4. Push to your branch
5. Open a Pull Request

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with:
- [Vyper](https://vyperlang.org/) - Smart contract language
- [Boa](https://github.com/vyperlang/titanoboa) - Testing framework
- [Hypothesis](https://hypothesis.works/) - Property-based testing
