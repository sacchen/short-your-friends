# Contributing quick start guide

## Setup
- Environment: `uv sync --all-groups`
- Pypy for benchmarks `uv python install pypy`

## Navigation
- Orderbook: `python-prototype/src/orderbook` contains the core data structures
- Entry point: `python-prototype/server.py` handles networking
- Currently refactoring `src/engine` to move into `engine/engine`

## Workflow
Run commands from `python-prototype` directory,
`python-prototype/Makefile` for common tasks:
- `make type-check`: Runs strict Mypy checks.
- `make bench`: Runs the matching engine benchmark with PyPy.
- `make test-local`: Runs the pytest suite.
- `make run-server`: Starts the TCP server (defaulting to the PYTHONPATH=src setup).
- To switch from the Droplet to local, edit the tcp_server line in `server.py` to point to 127.0.0.1.