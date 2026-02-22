# shortyourfriends

Binary prediction market prototype for betting on screen-time outcomes.

The project currently includes:
- A Python matching engine and TCP server (`python-prototype/`)
- An iOS client prototype (`ios-client/`)
- Architecture and learning notes (`ARCHITECTURE.md`, `python-prototype/logs/`)

## Repository map
- `python-prototype/`: backend engine, server, simulation scripts, and tests
- `ios-client/`: SwiftUI client using raw TCP messaging
- `ARCHITECTURE.md`: backend and client architecture reference
- `contributing.md`: contributor workflow and standards

## Current priorities
- CI quality gates are in place (`ruff`, `mypy`, unit + integration tests)
- Next infrastructure milestones:
  - Docker Compose local stack
  - PostgreSQL transactional persistence

Tracked in GitHub issues:
- `#3` Infrastructure hardening tracker
- `#4` PostgreSQL persistence
- `#5` CI quality gates
- `#6` Docker + Compose

## Quick start
Backend setup and commands live in `python-prototype/README.md`.

## Notes
- This repo uses integer cents for order-book prices to avoid floating-point errors.
- Persistence is currently JSON-based and planned for migration to PostgreSQL.
