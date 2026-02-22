# Architecture

This document is a high-signal reference for the current system.
For setup and commands, use `docs/DEVELOPER_GUIDE.md`.

## Information map
- Day-to-day commands: `docs/DEVELOPER_GUIDE.md`
- Backend runbook: `python-prototype/README.md`
- Contribution workflow: `CONTRIBUTING.md`
- Deep learning notes: `python-prototype/logs/`

## Current system (2026-02)

### Runtime components
- TCP server: `python-prototype/server.py`
- Interface boundary: `python-prototype/src/engine/interface.py`
- Matching engine: `python-prototype/src/engine/engine.py`
- Order book: `python-prototype/src/orderbook/book.py`
- Economy/accounting: `python-prototype/src/orderbook/economy.py`
- Invariant auditor: `python-prototype/src/orderbook/audit.py`
- User ID mapper: `python-prototype/src/orderbook/id_mapper.py`

### Client component
- iOS TCP client: `ios-client/ShortYourFriends/NetworkClient.swift`

## Layer model

### Layer 1: Server (I/O boundary)
`server.py` handles network concerns only:
- Newline-delimited JSON framing
- Request parsing and response formatting
- Delegation to `EngineInterface`

### Layer 2: EngineInterface (coordination boundary)
`interface.py` handles:
- Request translation (external strings/dicts -> internal engine types)
- Cross-cutting business flow:
  - lock funds
  - process order/cancel/settle
  - confirm trade effects
  - run audit

### Layer 3: Matching and data structures
- `MatchingEngine` manages multiple markets and global order registry
- `OrderBook` executes price-time matching for one market

## Core flow

```text
Client -> server.py -> translate_client_message()
      -> EngineInterface.execute()
      -> Economy lock/check
      -> MatchingEngine.process_order()
      -> Economy confirm/release
      -> SystemAuditor.run_full_audit()
      -> response to client
```

## Key invariants
- Contract conservation per market: net position sum must be 0.
- Cash conservation: available + locked remains consistent system-wide.
- Registry integrity: global order registry must match order books.

These are enforced/checked by `SystemAuditor` after critical operations.

## Data and persistence
- Current persistence: JSON snapshot file (`state.json`)
- Known limitation: non-transactional writes (not ACID)
- Planned migration: PostgreSQL transactional persistence (issue `#4`)

## Testing model
- Unit/invariant tests: run without server
- Integration tests: require live TCP server
- Marker split uses `integration` pytest marker

## Performance/precision decisions
- Prices are integer cents across engine paths.
- User IDs are mapped from external strings to internal integers.
- Order cancellation targets O(1) via global registry lookup.

## Near-term evolution
- Docker Compose local stack (issue `#6`)
- PostgreSQL as persistence source of truth (issue `#4`)

## Out-of-date or exploratory artifacts
- `python-prototype/logs/` files are educational notes and may not represent final implementation details.
- `python-prototype/server_cheatsheet.md` is an operations quick reference, not a source of design truth.
