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
  "economy": { ... },
  "mapper": { ... },
  "engine": {
    "markets": {
      "alice,480": {
        "name": "Alice Sleep 8:00 AM",
        "bids": [ { "price": 40, "qty": 10, "side": "buy", ... } ],
        "asks": [ ... ]
      }
    }
  }
}
```

**Key points:**
- Account balances: `Decimal` → `str`
- User ID map: `str` ↔ `int`
- Market IDs: Tuple `("alice", 480)` → string `"alice,480"`

### 2. Serialization Strategies
- **Decimal**: Converted to `str` via custom `JSONEncoder`
- **Tuples**: Market IDs `("alice", 60)` → string `"alice,60"` for JSON keys
- **Linked Lists**: `OrderBook` linked lists flattened into lists of dicts
- **Timestamps**: Original timestamps preserved during hydration to maintain FIFO priority

### 3. Hydration Logic
- **Economy**: Loads string values back into `Decimal`
- **Mapper**: Rebuilds bidirectional maps
- **Engine**: 
  - Parses `"alice,60"` string back to Tuple
  - Recreates markets with saved names
  - Repopulates `OrderBook` and restores original timestamps

---

## Questions to Understand

### 1. The "Key" Problem
Why did `engine.py` crash when reading `"alice,480"` from the JSON file, even though that's exactly what `server.py` wrote?

**Hint:** What type is a dictionary key in Python vs. JSON?

To figure this out, we would need to use the `type()` function and `print()`.
We would find that python memory uses `Type: <class 'tuple'>` and JSON uses `Type: <class 'str'>`.
Python dicts allow Tuples as keys, but JSON only allows Strings as keys. To save to JSON, we need the tuple to become a string. When we loaded it back, it was still a string. So we need to turn it into a tuple or else Engine couldn't parse it.

### 2. The "Box" Problem
Why couldn't we just dump `book._bids` directly to JSON? Why did we have to write a loop with `curr = curr.next`?

**Hint:** `_bids` is a dictionary of `OrderList` objects, not a list of numbers. JSON doesn't know how to look inside the custom classes.

We figure this out by looking at what `book._bids` contains. We can `print(book._bids)` and outputs says `{ 40: <OrderList object at 0x104a...> }`.
(`0x104a` is the base-16 memory address for the object. `0x` means hexadecimal and `104a` is some room number in memory for the object). We have to unpack the objects to save the contents instead of the address.

JSON knows what numbers and lists are, but not `OrderList object`. Python wouldn't know how to turn this object into text, so we loop to pull (id, price, qty) data out of the object and put it into dict and list format for JSON.

### 3. The "Fairness" Problem
If we didn't manually save and restore the `timestamp` field, what would happen to the priority of orders when the server restarts?

**Hint:** `add_order` defaults to "now". If everyone gets a new "now" at the same second, who goes first?

We figure this out by looking at the `add_order` function in `OrderBook`. It uses `timestamp = time.time()` to get the current time.

If we didn't save timestamps, when the server restarts, it will add past orders using the current time instead of the past time where the order was actually submitted. This also removes the Time Priority of orders. 

### 4. The "Type" Problem
Why does `server.py` need a custom `GameStateEncoder` for the economy but not for the engine?

**Hint:** The Economy uses `Decimal` for money. The Engine uses `int` for prices. Which one is standard JSON compatible?

We figure this out by checking the data types of the numbers. Economy uses `<class 'decimal.Decimal'>` and Engine uses `<class 'int'>`.

`GameStateEncoder` (renamed to `DecimalEncoder`) tells Python to treat Decimals as Strings.