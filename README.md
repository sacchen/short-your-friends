# shortyourfriends

**A prediction market for dopamine addiction.**

You short-sell your friends' bad habits. Capital is minted by walking and
burned by doomscrolling — so you have to stay off your phone to afford to
bet that your friends won't.

## How it works

**The economy.** Liquidity is capped by physical effort and drained by
digital consumption.

- **Proof of Walk** — you earn `0.01` credits per verified step
- **Doomscroll Burn** — you lose `5.00` credits per hour of screen time
- **The constraint** — you must be active to afford to short anyone

**The market.** Each contract is a binary bet on one person clearing one
threshold, identified as `(user, minutes)` — `alice,480` is "Alice stays
under 8 hours today."

- **Long** — bet they stay under
- **Short** — bet they fail
- **Settlement** — contracts resolve to exactly 0 or 1. No partial credit.

When the reported screen time crosses the threshold, the contract collapses
to zero and every short gets paid.

## What runs today

- **Matching engine** — price-time priority, multi-market, integer cents
- **Order book** — custom linked-list book with an O(1) cancellation registry
- **Economy** — accounts, positions, available vs. locked balances
- **Settlement** — binary resolution against a reported threshold crossing
- **Invariant auditing** — cash conservation, position and registry integrity
- **iOS client** — SwiftUI, browses markets over raw TCP
- **Infrastructure** — Docker Compose (`app` + `postgres`), CI running
  `ruff`, `mypy`, and unit + integration tests

## Not built yet

The exchange works. Nothing connects it to a real phone yet.

- **The oracle** — screen time currently arrives from `trigger_settle.py`,
  a script with a hardcoded number. Nothing observes a real phone.
- **Proof of Walk** — no `HealthKit` integration; steps are never read
- **The Snitch** — no `DeviceActivityMonitor`; nothing wakes on a threshold
- **Rust port** — the matching engine is Python, and staying that way for now
- **Persistence** — state lives in `state.json`; the PostgreSQL migration
  is the current focus

## The privacy problem

Apple's `DeviceActivity` API is deliberately privacy-preserving: it won't
export raw usage data or app names, so nothing can simply read your screen
time and report it.

The intended workaround is **Proof of Portfolio** — you pick a "portfolio of
shame" via `FamilyActivityPicker`, the app renders a sandboxed report of
those icons, and you export it to the group. Stuff it with Calculator and
Notes to game the burn rate, and you get delisted by hand.

## Look around

- [`python-prototype/logs/`](python-prototype/logs/) — six design decisions
  written up as they were made: order book structure, ID types, persistence,
  interface patterns, the iOS TCP client, and Postgres transactions
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system boundaries and data flow
- [`python-prototype/`](python-prototype/) — engine, book, economy, tests
- [`ios-client/`](ios-client/) — SwiftUI client
- [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) — commands and workflow
- [`docs/DOCKER.md`](docs/DOCKER.md) — local containerized setup
