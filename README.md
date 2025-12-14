# shortyourfriends

**A distributed prediction market for dopamine addiction.**

A high-frequency trading engine where users short-sell their friends' bad habits. Capital is minted via physical activity (steps) and liquidated by screen time thresholds.

---

## Components

The system is split into three distinct layers to simulate a real quantitative trading stack:

**Engine (Python/Rust):**
* *Current:* A Python implementation of a Limit Order Book (LOB) and matching engine. Serves as the primary backend for handling bid/ask matching and clearing trades.
* *Goal:* Porting the core matching logic to **Rust** to handle high-frequency concurrent requests and improve order execution latency.

**Simulation (Python):**
* Models market dynamics and economic incentives to tune the game.
* Simulates "Market Maker" bots to test liquidity and ensure the economy doesn't break.

**Client (Swift):**
* iOS app serving as the data oracle.
* *Mining:* Integrates with `HealthKit` to convert steps into tradeable capital.
* *The Snitch:* Uses `DeviceActivityMonitor` to trigger background webhooks when users cross local usage thresholds (e.g., crossing a 30m or 60m "doomscroll" limit).

---

## The Mechanism

### 1. The Economy (Capital Flow)
Liquidity is hard-capped by physical effort and drained by digital consumption.

* **UBI:** Daily base allowance of credits.
* **Income (Proof of Walk):** Earn $X credits per 1,000 verified steps.
* **Tax (Doomscroll Burn):** Lose $Y credits per hour of screen time.
* **Constraint:** You must be active to maintain the liquidity required to short others.

### 2. Trading (Binary Options)
The market trades daily contracts on user behavior (e.g., `$SAM_FOCUS`).

* **Long:** Bet the user stays under screen time thresholds.
* **Short:** Bet the user fails (crosses the threshold).
* **Settlement:** Contracts settle at 0 or 1 based on the Swift client's report.

### 3. Execution
Real-time liquidation process:

1.  User crosses a configured threshold (e.g., 60m on their selected apps).
2.  Client wakes up in background → Pings the backend engine.
3.  Contract collapses to $0.00 instantly.

---

## The Privacy Problem
Apple's `DeviceActivity` API is privacy-preserving; it blocks export of raw usage data or specific app names.

### The Workaround: Proof of Portfolio
* **Restriction:** Users must select a "Portfolio of Shame" (e.g., Instagram, TikTok, Hinge) via `FamilyActivityPicker`.
* **Verification:** App generates a sandboxed `DeviceActivityReport` rendering icons of selected apps.
* **Social Audit:** Users export this view to the group. If the portfolio contains safe apps (e.g., Calculator) to game the system, the user is manually delisted.

---

## Project Goals
* Implement a performant matching engine from scratch (starting in Python, moving to Rust).
* Explore financial data structures (Order Books, Matching Algorithms) in a non-trivial context.
* Navigate strict iOS privacy sandboxes to extract tradeable signals from health data.

---

## Status
* `/src/engine` - Python LOB implementation *(Active)*
* `/src/rust_port` - Rust Engine Port *(Planned)*
* `/src/client` - Swift DeviceActivity integration *(Prototype)*
