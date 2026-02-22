# Python Order Book Prototype

This is the reference implementation of the shortyourfriends matching engine.

It includes a TCP server, limit order book, and market dymamic simulation.

## To run demo

### Terminal 1: Engine
Start TCP server. Holds in-memory order book.
`PYTHONPATH=src uv run server.py`

### Terminal 2: Simulation
Start Market Maker (liquidity provider), Gambler (taker), and Ticker (visualization). Spreads will stabilize and orders will accumulate in book.
`PYTHONPATH=src uv run simulation.py`

### Terminal 3: Snitch
iOS client reports user has exceed screen time limit. In Terminal 2, order book will clear and positions will be settled.
`PYTHONPATH=src uv run trigger_settle.py`

## Test workflow

The suite is split into two categories:

- Unit/invariant tests: fast tests that do not require a running TCP server.
- Integration tests: socket-level tests that require a live server on `TEST_SERVER_HOST:TEST_SERVER_PORT`.

Run from `python-prototype`:

```bash
# Unit + invariant tests only (default for quick local checks/CI)
uv run pytest -m "not integration"

# Integration tests (start server in another terminal first)
TEST_SERVER_HOST=127.0.0.1 TEST_SERVER_PORT=8888 uv run pytest -m integration
```

To mirror the CI quality gate locally:

```bash
uv run ruff check .
uv run mypy
uv run pytest -m "not integration"
```

## File structure
- `server.py`: Async TCP server that routes JSON requests to engine.

- `simulation.py`: Runs bots and Bloomberg Terminal view.

- `trigger_settle.py`: Sends the settlement payload (Snitch).

- `src/orderbook/`: Core logic (Book, Matching, Trade Types).
