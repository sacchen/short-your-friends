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

## File structure
- `server.py`: Async TCP server that routes JSON requests to engine.

- `simulation.py`: Runs bots and Bloomberg Terminal view.

- `trigger_settle.py`: Sends the settlement payload (Snitch).

- `src/orderbook/`: Core logic (Book, Matching, Trade Types).