# Python backend

Reference backend for the shortyourfriends exchange prototype.

Primary command reference: `../docs/DEVELOPER_GUIDE.md`
Containerized local stack: `../docs/DOCKER.md`

Includes:
- Async TCP server (`server.py`)
- Matching engine + order book (`src/engine`, `src/orderbook`)
- Simulation scripts (`simulation.py`, `trigger_settle.py`)
- Test suite (`tests/`)

## Setup

From `python-prototype/`:

```bash
uv sync --all-groups
```

## Run locally

Start server:

```bash
make run-server
```

Run simulation:

```bash
PYTHONPATH=src uv run simulation.py
```

Trigger settlement event:

```bash
PYTHONPATH=src uv run trigger_settle.py
```

## Tests

Test categories:
- Unit/invariant tests: no live server required
- Integration tests: require a running server

Commands:

```bash
make test-unit
make test-integration
```

Local CI equivalent:

```bash
make ci-check
```

## Useful commands

```bash
make type-check
make bench
```

## Notes

- Prices are represented as integer cents in engine/server paths.
- Current persistence is JSON (`state.json`); PostgreSQL migration is tracked in issue `#4`.
- Server state file path can be overridden with `STATE_FILE` (used by Docker Compose).
