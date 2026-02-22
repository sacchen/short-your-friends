# shortyourfriends

`shortyourfriends` is a systems-focused prediction market prototype.

Users trade binary contracts on screen-time outcomes, backed by a custom limit order book and matching engine.

## What you are looking at
- A working Python exchange backend (TCP server + matching engine)
- An iOS client prototype that talks to the backend over raw TCP
- Automated CI for linting, type checks, unit tests, and integration tests

This is not a SaaS app yet. It is an engineering prototype focused on trading-system architecture, correctness, and infrastructure hardening.

## Implemented today
- Price-time matching engine with multi-market support
- O(1)-style global order cancellation registry
- Economy/accounting layer with locked vs available balances
- Invariant auditing (positions, cash conservation, registry consistency)
- End-to-end socket integration tests against a live server
- GitHub Actions CI gates:
  - `ruff`
  - `mypy`
  - `pytest` (unit/invariant)
  - `pytest` (integration)

## In progress
- Docker Compose local stack
- PostgreSQL transactional persistence (replacing JSON snapshots)

## Tech stack
- Backend: Python 3.13+, `uv`, `pytest`, `mypy`, `ruff`
- Client: SwiftUI + Network.framework
- Protocol: newline-delimited JSON over TCP

## Repository guide
- `python-prototype/`: backend code, tests, simulation scripts
- `ios-client/`: Swift client prototype
- `ARCHITECTURE.md`: concise system design reference
- `docs/DEVELOPER_GUIDE.md`: contributor command guide
- `docs/DOCKER.md`: Docker Compose local stack guide
- `CONTRIBUTING.md`: contribution workflow

## Quick evaluation path
If you want to evaluate this project quickly:
1. Read `ARCHITECTURE.md` for system boundaries.
2. Open `.github/workflows/ci.yml` for quality gates.
3. Open `python-prototype/tests/` for behavioral coverage.
4. Run backend checks via `docs/DEVELOPER_GUIDE.md`.

## Design constraints
- Engine prices are integer cents (no floating-point money math).
- Current persistence is JSON (`state.json`) and intentionally marked for migration to PostgreSQL transactions.
