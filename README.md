# shortyourfriends

**A distributed prediction market for dopamine addiction.**

A trading-system prototype where users short-sell their friends' bad habits. Capital is minted via physical activity and liquidated by screen time thresholds.

## What This Repo Is

This repository is an engineering prototype, not a finished product.

It currently contains:
- A working Python exchange backend with a custom limit order book and TCP server
- An iOS client prototype that talks to the backend over raw TCP
- CI for linting, type-checking, unit tests, and integration tests

If you are evaluating the project, the most relevant files are:
- `ARCHITECTURE.md`
- `python-prototype/`
- `.github/workflows/ci.yml`

## Components

The system is split into three layers to model a small trading stack:

**Engine (Python):**
- Custom matching engine and order book
- Multi-market support
- Invariant auditing for cash, positions, and registry integrity

**Simulation (Python):**
- Scripts for driving market activity and settlement flows
- Useful for testing the exchange loop outside the iOS client

**Client (Swift):**
- iOS prototype using `Network.framework`
- Intended to act as the data oracle for activity and screen-time events

## The Mechanism

### 1. Economy
Liquidity is tied to behavior:

- **Income:** credits earned from physical activity
- **Penalty:** credits burned when screen-time thresholds are crossed
- **Constraint:** users need capital to take positions

### 2. Trading
Markets are binary contracts on user outcomes.

- **Long:** bet the user stays under a threshold
- **Short:** bet the user fails
- **Settlement:** contracts resolve based on the reported outcome

### 3. Execution
The backend receives events, matches orders, updates balances, and settles markets.

## What Is Implemented Today

- Price-time matching engine
- Global order registry for efficient cancellation
- Economy/accounting layer with available vs locked balances
- JSON persistence (`state.json`)
- End-to-end socket integration tests
- Docker Compose local stack (`app` + `postgres`)

## Current Engineering Focus

- Replace JSON persistence with PostgreSQL transactions
- Continue hardening local/dev infrastructure

## Design Constraints

- Prices are represented as integer cents in engine/server paths
- The TCP protocol uses newline-delimited JSON
- Current persistence is JSON-based and intentionally being migrated

## Where To Go Next

- `ARCHITECTURE.md`: system boundaries and data flow
- `docs/DEVELOPER_GUIDE.md`: commands and contributor workflow
- `docs/DOCKER.md`: local containerized setup
- `python-prototype/README.md`: backend-specific runbook
