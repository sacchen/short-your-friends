# User ID Type Decision
*Dec 24, 2025*

## Problem
Currently we have inconsistent types for `user_id`:
- API/Economy uses `str` (eg `"alice"`, `"test_user_1`)
- Matching engine uses `int` for performance

This requires conversions between layers and inconsistent types.

## Decision: Use both `str` and `int` with ID Mapping

### Architecture
┌─────────────────┐
│  API Layer      │  user_id: str  (human-readable, flexible)
│  (Python)       │  - Accepts strings, UUIDs, usernames
└────────┬────────┘
         │
         │ Convert at boundary: UserIdMapper.to_internal()
         ▼
┌─────────────────┐
│  Economy        │  user_id: str  (accounts, balances)
│  (Python)       │  - Human-readable for debugging
└────────┬────────┘
         │
         │ Convert at boundary: UserIdMapper.to_internal()  
         ▼
┌─────────────────┐
│  Matching       │  user_id: int  (internal ID)
│  Engine         │  - Fast comparisons
│  (Python/Rust)  │  - Flexible for Rust porting
└─────────────────┘

### Why

** Why `str` in API/Economy: **
- Human-readable for debugging/logging
- Flexible for UUIDs, usernames, emails
- JSON APIs

** Why `int` in Matching Engine **
- Performance for lots of matching: faster comparisons, less memory.
- Rust: maps to `i32`/`i64`

### Implementation

Use `UserIdMapper` class for conversion
- Map string to sequential int IDs
- Happens once per order at boundary
- Bidirectional for trade settling

### Adding Rust
- Use `i32`/`i64` for user IDs
- No strings for engine
- Good boundary

## Current state
- Economy uses `str`
- Engine uses `int`

- About to add `UserIdMapper` at boundary
- Then update `server.py` to use mapper
- Update types
- Add mapper tests