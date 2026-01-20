# ARCHITECTURE.md

## System Overview
**3-Layer Python Backend:**
- **EngineInterface:** API boundary handling type conversions and coordination.
- **MatchingEngine:** Multi-market manager with O(1) cancellations.
- **OrderBook:** Hybrid heap+FIFO structures for matching.

**Key Properties:**
- O(1) order cancellation via global registry.
- Conservation laws enforced by SystemAuditor.
- State persistence via JSON.

## CORE MODULES/SERVICES

### Python Backend (3-Layer Architecture)

#### Layer 1: EngineInterface (`src/engine/interface.py`)
**Responsibility:** API boundary layer between TCP server and matching engine
- Type conversions: string user IDs ↔ ints, dollars ↔ cents, UUID ↔ stable IDs
- Command dispatch: PLACE_ORDER, CANCEL_ORDER, SETTLE_MARKETS, GET_MARKETS, GET_SNAPSHOT
- Cross-cutting coordination: economy + engine + auditing

**Public Interface:**
```python
execute(cmd: EngineCommand) -> EngineResponse
translate_client_message(msg: dict) -> EngineCommand
```

**Dependencies:**
- MatchingEngine (matching logic)
- EconomyManager (capital flow)
- UserIdMapper (ID translation)
- SystemAuditor (invariant validation)

---

#### Layer 2: MatchingEngine (`src/engine/engine.py`)
**Responsibility:** Multi-market order book manager
- Manages `_markets: dict[MarketId, OrderBook]` (independent book per market)
- Global registry `_order_registry: dict[int, OrderMetadata]` enables O(1) order cancellation across all markets
- State persistence (JSON serialization)

**Public Interface:**
```python
process_order(market_id, side, price, qty, order_id, user_id) -> list[Trade]
cancel_order(order_id) -> OrderMetadata | None
settle_markets_for_user(target_user_id, actual_screentime_minutes) -> list[Trade]
get_active_markets() -> list[dict]
get_market_snapshot(market_id) -> dict
dump_state() / load_state()
```

**Dependencies:**
- OrderBook (delegates per-market operations)

---

#### Layer 3: OrderBook (`src/orderbook/book.py`)
**Responsibility:** Single market's order matching logic
- Hybrid data structure:
  - `_orders: dict[int, OrderNode]` - O(1) lookup
  - `_bids/asks: dict[int, OrderList]` - Price → FIFO LinkedList
  - `_bids_heap/asks_heap: list[int]` - Max/Min heap for price priority (lazy deletion)
  - `_positions: dict[int, int]` - Net quantity per user
- Matching algorithm: O(log n) heap operations, O(1) linked list removal

**Public Interface:**
```python
process_order(side, price, qty, order_id, user_id) -> list[Trade]
cancel_order(order_id) -> None
settle_market(terminal_price: int) -> list[Trade]
snapshot() -> dict
add_order(side, price, qty, order_id, user_id) -> None
```

**Dependencies:**
- OrderList (`linked_list.py`) - FIFO queue per price level
- OrderNode (`node.py`) - Doubly-linked list node
- Trade (`trade.py`) - Immutable trade record

---

### Supporting Services

#### EconomyManager (`src/orderbook/economy.py`)
**Responsibility:** User accounts, capital flow, portfolio tracking
- `accounts: dict[str, Account]` - User balances (available + locked) + portfolio positions
- Gamification: Proof of Walk (mint credits), Doomscroll Tax (burn credits), UBI distribution

**Public Interface:**
```python
get_account(user_id: str) -> Account
process_proof_of_walk(user_id: str, steps: int) -> Decimal
process_doomscroll_burn(user_id: str, minutes: int) -> Decimal
attempt_order_lock(user_id: str, price: Decimal, qty: int) -> bool
release_order_lock(user_id: str, price: Decimal, qty: int) -> None
confirm_trade(buyer_id, seller_id, market_id, price, qty) -> None
distribute_ubi(amount: Decimal) -> None
dump_state() / load_state()
```

**Dependencies:** None

---

#### UserIdMapper (`src/orderbook/id_mapper.py`)
**Responsibility:** Convert string user IDs (external API) to integers (engine performance)
- `_str_to_int: dict[str, int]` and `_int_to_str: dict[int, str]`
- Auto-assigns IDs on first use

**Public Interface:**
```python
to_internal(user_id: str) -> int
to_external(user_id: int) -> str
dump_state() / load_state()
```

**Dependencies:** None

---

#### SystemAuditor (`src/orderbook/audit.py`)
**Responsibility:** Enforce system invariants
- Conservation of contracts: sum(positions per market) = 0
- Conservation of cash: available + locked = total system liquidity
- Registry integrity: global registry matches book state

**Public Interface:**
```python
run_full_audit() -> None
```

**Dependencies:**
- MatchingEngine._order_registry (read-only)
- EconomyManager.accounts (read-only)

---

#### Server (`server.py`)
**Responsibility:** TCP server (asyncio), JSON request/response framing
- Newline-delimited JSON over TCP
- Routes requests to EngineInterface

**Public Interface:**
```python
handle_client(reader, writer) -> None
process_request(request: dict) -> dict
```

**Dependencies:**
- EngineInterface (execute commands)
- UserIdMapper (translate messages)

---

### iOS Client (Swift)

#### NetworkClient (`ios-client/ShortYourFriends/NetworkClient.swift`)
**Responsibility:** TCP connection manager, state management
- Published state: `@Published var markets, positions, balance, isConnected`
- TCP framing: accumulates `incomingBuffer`, splits on `\n` delimiter
- Price conversions: dollars (UI) ↔ cents (server)

**Public Interface:**
```swift
func connect(host: String, port: UInt16)
func send(request: [String: Any])
func fetchMarkets()
func placeOrder(marketId: String, side: String, price: Double, qty: Int)
```

**Dependencies:**
- Network.framework (NWConnection for TCP)

---

#### Views (`MarketListView.swift`, `MarketDetailView.swift`)
**Responsibility:** SwiftUI UI, observes NetworkClient state
- MarketListView: displays market list
- MarketDetailView: order form + market depth

**Dependencies:**
- NetworkClient (ObservableObject)
- Models.swift (Market, Position, GenericResponse)

---

## DATA FLOW

### Inbound Request Flow
```
Client JSON → Server.handle_client()
           → Server.process_request()
           → EngineInterface.translate_client_message()
               [string user IDs → ints, dollars → cents]
           → EngineInterface.execute(EngineCommand)
               [dispatch to handler]
           → Handler (e.g., _handle_place_order)
               ├─ Lock funds (EconomyManager.attempt_order_lock)
               ├─ Execute matching (MatchingEngine.process_order)
               │  └─ OrderBook.process_order() → list[Trade]
               ├─ Confirm trades (EconomyManager.confirm_trade)
               ├─ Price improvement refunds
               └─ Audit (SystemAuditor.run_full_audit)
           → EngineResponse
           → Server.process_request() [format response]
               [ints → strings, cents → dollars]
           → JSON response over TCP
           → Client
```

### Order Matching Flow (OrderBook)
```
process_order(side, price, qty, order_id, user_id)
    ↓
[Matching Phase]
    If BUY: pop _asks_heap (min price)
        For each seller at price level (FIFO via OrderList):
            ├─ Calculate trade_qty = min(remaining_qty, maker_qty)
            ├─ Create Trade
            ├─ Update _positions
            └─ Remove filled orders from _orders + OrderList
    If SELL: pop _bids_heap (max price) [same logic]
    ↓
[Resting Phase]
    If remaining_qty > 0:
        ├─ Create OrderNode
        └─ Add to _bids/_asks dict + heap
    ↓
Return list[Trade]
```

### Settlement Flow
```
Client POST settle {target_user_id, actual_screentime_minutes}
    ↓
EngineInterface._handle_settle()
    ├─ terminal_price = 1 if screentime >= threshold else 0
    ├─ For each market where market_id[0] == target_user_id:
    │  └─ OrderBook.settle_market(terminal_price)
    │     ├─ Set active = False
    │     ├─ Cancel all resting orders
    │     └─ Create synthetic trades:
    │        - Long positions: receive terminal_price per contract
    │        - Short positions: pay terminal_price per contract
    └─ EconomyManager.confirm_trade() [process synthetic trades]
```

### iOS Client Flow
```
User action (e.g., "Buy")
    ↓
MarketDetailView.placeOrder()
    ├─ Convert price: dollars × 100 → cents
    └─ NetworkClient.placeOrder()
    ↓
NetworkClient.send(request)
    ├─ Serialize [String: Any] → JSON
    ├─ Append '\n' delimiter
    └─ NWConnection.send() [TCP]
    ↓
NetworkClient.receive() [async loop]
    ├─ Read TCP bytes → incomingBuffer
    ├─ processBuffer() [split on '\n']
    └─ handleMessage(json)
        ├─ JSONDecoder.decode(GenericResponse)
        └─ Update @Published properties → SwiftUI re-renders
```

---

## KEY INTERFACES

### EngineInterface
- `execute(EngineCommand) -> EngineResponse` - Central dispatcher
- `_handle_place_order()` - Coordinates economy + engine + auditing
- `_handle_cancel_order()` - Cancel + release funds
- `_handle_settle()` - Settle markets + confirm trades
- `_handle_get_markets()` - Return market list with best bid/ask
- `_handle_get_snapshot()` - Return bids/asks for market

### MatchingEngine
- `process_order(market_id, side, price, qty, order_id, user_id) -> list[Trade]`
- `cancel_order(order_id) -> OrderMetadata | None` - O(1) via global registry
- `settle_markets_for_user(target_user_id, actual_screentime_minutes) -> list[Trade]`
- `get_active_markets() -> list[dict]`
- `dump_state()` / `load_state()` - Persistence

### OrderBook
- `process_order(side, price, qty, order_id, user_id) -> list[Trade]` - Match + rest
- `cancel_order(order_id) -> None` - O(1) removal
- `settle_market(terminal_price: int) -> list[Trade]` - Close market, synthetic trades
- `snapshot() -> dict` - Return {"bids": [...], "asks": [...]}

### EconomyManager
- `attempt_order_lock(user_id, price, qty) -> bool` - Lock funds for buy order
- `release_order_lock(user_id, price, qty)` - Refund locked funds
- `confirm_trade(buyer_id, seller_id, market_id, price, qty)` - Transfer cash + update portfolio
- `process_proof_of_walk(user_id, steps) -> Decimal` - Mint credits
- `process_doomscroll_burn(user_id, minutes) -> Decimal` - Burn credits

### NetworkClient (iOS)
- `connect(host, port)` - Establish TCP connection
- `send(request: [String: Any])` - Send JSON over TCP
- `fetchMarkets()` - Request market list
- `placeOrder(marketId, side, price, qty)` - Submit order

---

## CRITICAL DEPENDENCIES

### Dependency Graph
```
Server (TCP)
    ↓
EngineInterface (API boundary)
    ├─ MatchingEngine
    │  └─ OrderBook × N (per market)
    │     ├─ OrderList (FIFO per price)
    │     └─ OrderNode (doubly-linked)
    ├─ EconomyManager
    ├─ UserIdMapper
    └─ SystemAuditor
        ├─ MatchingEngine._order_registry (read)
        └─ EconomyManager.accounts (read)
```

### Key Coupling Points
| Component | Depends On | Interface |
|-----------|-----------|-----------|
| EngineInterface | MatchingEngine | `process_order()`, `cancel_order()`, `settle_markets_for_user()` |
| EngineInterface | EconomyManager | `attempt_order_lock()`, `release_order_lock()`, `confirm_trade()` |
| EngineInterface | UserIdMapper | `to_internal()`, `to_external()` |
| EngineInterface | SystemAuditor | `run_full_audit()` |
| MatchingEngine | OrderBook | `process_order()`, `cancel_order()`, `settle_market()` |
| OrderBook | OrderList/OrderNode | `append()`, `remove()` |
| Server | EngineInterface | `execute(EngineCommand)` |
| Server | UserIdMapper | `translate_client_message()` |

### Data Ownership
| Component | Owns | Reads |
|-----------|------|-------|
| EngineInterface | None (facade) | Engine, Economy, Auditor state |
| MatchingEngine | `_markets`, `_market_names`, `_order_registry` | OrderBook state |
| OrderBook | `_orders`, `_bids`, `_asks`, `_bids_heap`, `_asks_heap`, `_positions` | None |
| EconomyManager | `accounts` | None |
| UserIdMapper | `_str_to_int`, `_int_to_str` | None |
| SystemAuditor | None (read-only) | MatchingEngine, EconomyManager state |

---

## SYSTEM INVARIANTS

### Enforced by SystemAuditor
1. **Conservation of Contracts:** `sum(positions per market) = 0`
2. **Conservation of Cash:** `available + locked = total system liquidity`
3. **Registry Integrity:** Global `_order_registry` matches book state

### Business Constraints
- **Price Units:** Engine uses cents (integers) to avoid floating-point errors
- **User ID Mapping:** External APIs use strings (usernames), engine uses integers (performance)
- **Market Closure:** Once settled, market is "inactive" (no new orders accepted)
- **Settlement Logic:** `terminal_price = 1 if actual_screentime >= threshold else 0`

---

## PERSISTENCE

### State Files
- `state.json` - Combined state (engine + economy + user_id_mapper)

### Startup Sequence
1. `Server.__init__()`
2. Load saved state:
   - `engine.load_state()` → restore markets and orders
   - `economy.load_state()` → restore accounts, balances, portfolios
   - `user_id_mapper.load_state()` → restore ID mappings
3. `auditor.run_full_audit()` → verify no corruption
4. Resume operations

### Serialization Format
```json
{
  "engine": {
    "markets": {
      "1,480": {
        "name": "Alice Sleep Schedule",
        "bids": [{"id": 12345, "user_id": 2, "price": 40, "qty": 5, "side": "buy", "timestamp": 1234567}],
        "asks": [...]
      }
    }
  },
  "economy": {
    "alice": {
      "available": "150.50",
      "locked": "25.00",
      "portfolio": {"alice,480": 10, "bob,600": -5}
    }
  },
  "user_id_mapper": {
    "map": {"alice": 1, "bob": 2},
    "next_id": 3
  }
}
```

---

## CRITICAL FILE PATHS

### Python Backend
- `python-prototype/server.py` - TCP server entry point
- `python-prototype/src/engine/engine.py` - MatchingEngine
- `python-prototype/src/engine/interface.py` - EngineInterface
- `python-prototype/src/orderbook/book.py` - OrderBook
- `python-prototype/src/orderbook/economy.py` - EconomyManager
- `python-prototype/src/orderbook/id_mapper.py` - UserIdMapper
- `python-prototype/src/orderbook/audit.py` - SystemAuditor

### iOS Client
- `ios-client/ShortYourFriends/NetworkClient.swift` - TCP client
- `ios-client/ShortYourFriends/Models.swift` - Data structures
- `ios-client/ShortYourFriends/MarketListView.swift` - Main UI
- `ios-client/ShortYourFriends/MarketDetailView.swift` - Order form + depth

### Simulation/Testing
- `python-prototype/simulation.py` - Market maker + taker bots
- `python-prototype/trigger_settle.py` - Settlement trigger
