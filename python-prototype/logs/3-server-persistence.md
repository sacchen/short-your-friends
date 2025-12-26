# Server Persistence & Serialization
*Dec 25, 2025*

## Problem
The server lost all state (user balances, open orders, ID mappings) on restart.
Standard `json.dump` failed because of non-serializable types:
- `Decimal` (Economy)
- `Tuple` keys (Market IDs in Engine)
- `OrderNode` linked lists (OrderBook)

## Solution: State.json
Implemented a `save_world()` and `load_world()` system in `server.py` that serializes three core components to `state.json`.

### 1. Data Schema
The JSON structure is:
```json
{
  "economy": { ... },    // Account balances (Decimal -> Str)
  "mapper": { ... },     // User ID map (Str <-> Int)
  "engine": {
    "markets": {
      "alice,480": {     // Key sanitized from Tuple ("alice", 480)
        "name": "Alice Sleep 8:00 AM",
        "bids": [ { "price": 40, "qty": 10, "side": "buy", ... } ],
        "asks": [ ... ]
      }
    }
  }
}
```

### 2. Serialization Strategies
* **Decimal**: Converted to `str` via custom `JSONEncoder`.
* **Tuples**: Market IDs `("alice", 60)` converted to string `"alice,60"` for JSON keys.
* **Linked Lists**: `OrderBook` linked lists are flattened into lists of dicts.
* **Timestamps**: Original timestamps are preserved during hydration to maintain FIFO priority.

### 3. Hydration Logic
* **Economy**: Loads string values back into `Decimal`.
* **Mapper**: Rebuilds bidirectional maps.
* **Engine**: 
  - Parses `"alice,60"` string back to Tuple.
  - Recreates markets with saved names.
  - Repopulates `OrderBook` and restores original timestamps.