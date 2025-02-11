# Leviathan Auction House

**Please read this entire document carefully to ensure the proper setup of each component.**

## Installation

### Creating a Virtual Environment

It is **strongly recommended** use a virtual environment with this project. This ensures that dependencies are strictly contained within your project and will not alter or affect your other development environment.

To create a new virtual environment and install the required dependencie:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_complete.txt
```

In future sessions, activate the virtual environment with:

```bash
source venv/bin/activate
```

To learn more about `venv`, see the official [Python documentation](https://docs.python.org/3/library/venv.html).

## Setting up your .env file

The config requies a `.env` file to exist.
Run `cp example.env .env` to create one and update.

```bash
pytest
```

You can use the `--gas` flag to estimate gas usage

### Linting
These same commands are run in our CI so make sure to run them locally before pushing or the checks might fail. 

To lint Vyper files
```bash
mamushi
```

To lint Python files
```bash
black <path_to_file>
```

## License

This project is licensed under the [MIT license](LICENSE).


### Tests
Run standard tests
```
pytest
```

Tests for fork mode
```
pytest tests/fork --fork
pytest tests/hypothesis --fork
```

```
pytest --cov= --cov-branch tests/native
coverage html
```
