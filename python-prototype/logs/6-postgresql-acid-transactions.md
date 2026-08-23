# PostgreSQL & ACID Transactions
*Jan 20, 2026*

## The Core Problem

Our `state.json` approach has a fatal flaw: **non-atomic writes**.

```python
# What we do now
def save_world(self):
    data = {
        "economy": self.economy.dump_state(),    # Step 1
        "engine": self.engine.dump_state(),      # Step 2
        "mapper": self.user_id_mapper.dump_state() # Step 3
    }
    with open(DB_FILE, "w") as f:
        json.dump(data, f)                       # Step 4
```

If the server crashes between Step 2 and Step 4, we have **inconsistent state**:
- Economy was read at time T1
- Engine was read at time T2
- Neither made it to disk

On restart, we load stale data. The auditor will scream.

---

## ACID: The Four Pillars

### Atomicity
**All or nothing.** A transaction either completes entirely or has no effect.

```sql
-- Example: Transfer $100 from Alice to Bob
BEGIN TRANSACTION;
UPDATE accounts SET balance = balance - 100 WHERE user_id = 'alice';
UPDATE accounts SET balance = balance + 100 WHERE user_id = 'bob';
COMMIT;
```

If the system crashes after the first UPDATE but before COMMIT, **both changes are rolled back**. Alice keeps her $100.

**JSON equivalent:** Impossible. `json.dump()` is one operation, but collecting the data is many operations.

### Consistency
**The database is always in a valid state.** Constraints prevent illegal data.

```sql
-- PostgreSQL enforces this at write time
CREATE TABLE accounts (
    user_id TEXT PRIMARY KEY,
    balance_available NUMERIC(20, 2) CHECK (balance_available >= 0),
    balance_locked NUMERIC(20, 2) CHECK (balance_locked >= 0)
);
```

**JSON equivalent:** None. We detect violations *after* they're written via `SystemAuditor`.

### Isolation
**Concurrent transactions don't interfere.** Each sees a consistent snapshot.

What happens with JSON if two requests hit `save_world()` simultaneously?
1. Request A reads economy, engine, mapper
2. Request B reads economy, engine, mapper (with slightly different state)
3. Request A writes to file
4. Request B overwrites the file

Request A's changes are lost. This is called a **lost update**.

PostgreSQL uses **MVCC (Multi-Version Concurrency Control)** to prevent this.

### Durability
**Committed data survives crashes.** Once you get "COMMIT OK", it's on disk.

```python
# Python file writes are NOT durable by default
with open("data.json", "w") as f:
    json.dump(data, f)
# OS may still be buffering! Power loss = data loss
```

PostgreSQL uses **Write-Ahead Logging (WAL)**:
1. Write changes to WAL (sequential, fast)
2. Acknowledge COMMIT to client
3. Later, apply WAL to actual data files

If crash happens, replay WAL on startup to recover.

---

## Questions to Understand

### 1. Why can't we just save more frequently?

**Hint:** Think about what "atomic" means. If you save economy, then engine, then mapper as 3 separate operations, how many atomic units do you have?

We figure this out by counting the failure points. With 3 saves, we have 3 chances for a crash between saves. Each save is atomic, but the *combination* is not. You need **one atomic operation** that saves everything, not many small ones.

### 2. Why use `asyncpg` instead of `psycopg2`?

**Hint:** Look at `server.py`. What concurrency model does it use? What happens if a blocking call runs inside an `async` function?

We figure this out by checking the server's architecture. `server.py` uses `asyncio`. If we call `psycopg2` (synchronous) inside an async handler, it would **block the entire event loop** — no other clients could be served during the query.

```python
# asyncpg is non-blocking
async with pool.acquire() as conn:
    result = await conn.fetch("SELECT * FROM accounts")  # Other tasks run during I/O wait
```

### 3. What's connection pooling and why do we need it?

**Hint:** Try timing `asyncpg.connect()` vs `pool.acquire()`. What's the difference?

We figure this out by benchmarking. Creating a new database connection takes ~50-100ms (TCP handshake, authentication, etc.). A pool keeps connections open and reuses them:

```python
pool = await asyncpg.create_pool(dsn, min_size=5, max_size=20)
# 5 connections ready immediately — no wait
# Up to 20 if load increases (then new requests queue)
```

### 4. How do we handle `Decimal` in PostgreSQL?

**Hint:** What type does PostgreSQL use for exact decimal math? Check the asyncpg docs for type mapping.

We figure this out by reading PostgreSQL docs. `NUMERIC(precision, scale)` is exact like Python's `Decimal`. asyncpg automatically converts between them:

```sql
balance_available NUMERIC(20, 2)  -- Up to 20 digits, 2 after decimal
```

### 5. What about our tuple Market IDs like `(1, 480)`?

**Hint:** JSON forced us to use strings like `"1,480"`. Does SQL have the same limitation?

We figure this out by checking SQL primary key options:
1. **Composite Primary Key:** `PRIMARY KEY (target_user, threshold_minutes)` — matches our domain!
2. **Generated ID:** Add a serial `id` column, store tuple as separate columns
3. **String Key:** Store as `"1,480"` like JSON (not recommended)

Option 1 is cleanest because it preserves the semantic meaning of our MarketId tuple.

---

## Schema Design Notes

### Tables and Relationships

```
user_mappings
├── external_id (PK): "alice"
└── internal_id (UNIQUE): 1

accounts
├── user_id (PK, FK → user_mappings.external_id): "alice"
├── balance_available: 150.50
└── balance_locked: 25.00

markets
├── target_user (PK, FK → user_mappings.internal_id): 1
├── threshold_minutes (PK): 480
├── name: "Alice Sleep 8:00 AM"
└── active: true

positions
├── user_id (FK → accounts): "alice"
├── market_target_user (FK → markets): 1
├── market_threshold (FK → markets): 480
├── quantity: 10
└── avg_entry_price: 0.45

orders
├── order_id (PK): 12345
├── market_target_user (FK): 1
├── market_threshold (FK): 480
├── user_id (FK): "alice"
├── side: "buy"
├── price: 40
├── quantity: 5
└── timestamp: 1234567890

trades (NEW - we don't persist these currently!)
├── id (PK): 1
├── market_target_user, market_threshold (FK)
├── buyer_id, seller_id (FK)
├── price: 45
├── quantity: 3
└── timestamp: 1234567890
```

### Key Insight: Trades Table
We currently throw away trade data after matching! With a `trades` table:
- Audit trail for disputes
- Historical price data for charts
- Analytics (volume, user activity)

---

## Migration Strategy

### Phase 1: Add PostgreSQL alongside JSON
1. Write to both JSON and PostgreSQL
2. Read from JSON (proven)
3. Compare results to validate PostgreSQL

### Phase 2: Switch to PostgreSQL
1. Read from PostgreSQL on startup
2. Remove JSON writes
3. Keep JSON as manual backup option

### Phase 3: Clean up
1. Remove JSON persistence code
2. Add database-backed auditor checks
3. Performance tuning

---

## Commands Cheatsheet

```bash
# PostgreSQL on macOS
brew install postgresql@16
brew services start postgresql@16

# Create database
createdb short_your_friends

# Connect via psql
psql short_your_friends

# Python
uv add asyncpg
```

---

## Resources

- [asyncpg documentation](https://magicstack.github.io/asyncpg/)
- [PostgreSQL ACID](https://www.postgresql.org/docs/current/transaction-iso.html)
- [MVCC Explained](https://www.postgresql.org/docs/current/mvcc.html)
