# Learning Log 5: iOS TCP Client Architecture

**Date:** 2026-01-02
**Context:** Documenting the iOS Swift client for educational understanding
**Related:** Issue #2, Commit c44219f

## The Problem: Client-Server Type Bridging

After refactoring the Python backend to use `EngineInterface` (logs/4), we needed to document how the iOS client communicates with the server. The challenge: bridging Swift and Python type systems while maintaining financial precision.

## Key Concepts Learned

### 1. Why Cents, Not Dollars?

**The Floating-Point Trap:**
```python
# Python (and most languages)
0.1 + 0.2 == 0.3  # False! Returns 0.30000000000000004
```

**The Solution: Integer Arithmetic**
```python
# Server (Python)
10 + 20 == 30  # Always true (cents)
```

**Lesson:** Financial systems MUST use integers (cents) to avoid precision errors. Dollars are for humans, cents are for computers.

### 2. TCP vs HTTP: When to Use Raw Sockets

**Why We Chose TCP:**
- Lower latency (no HTTP header overhead)
- Persistent connection (no reconnect per request)
- Custom protocol flexibility

**When HTTP Makes Sense:**
- REST APIs with standard CRUD operations
- Caching (HTTP headers)
- Load balancing

**Lesson:** For custom protocols with persistent connections (game servers, order books, chat), raw TCP is more efficient than HTTP.

### 3. The Framing Problem

**The Core Issue:**
TCP is a **stream protocol**, not a message protocol. Data arrives as a continuous stream of bytes:

```
Chunk 1: {"type":"get_mar
Chunk 2: kets"}\n{"type":"bal
Chunk 3: ance"}\n
```

**The Solution: Buffer + Delimiter**
```swift
private var incomingBuffer: String = ""

private func processBuffer() {
    while let range = incomingBuffer.range(of: "\n") {
        let message = String(incomingBuffer[..<range.lowerBound])
        incomingBuffer.removeSubrange(..<range.upperBound)
        handleMessage(message)
    }
}
```

**Why Newline (`\n`)?**
- Simple to implement
- JSON-safe (no `\n` inside valid JSON)
- Human-readable for debugging
- Industry standard (Redis, Memcached use similar patterns)

**Lesson:** When building on TCP, you MUST solve the framing problem. Common solutions:
1. Length-prefixed (binary protocols)
2. Delimiter-based (our approach)
3. Fixed-size messages

### 4. Network.framework vs URLSession

**Apple's Network Stack:**
```
Application Layer (7) ← URLSession (HTTP/HTTPS)
Transport Layer (4)   ← Network.framework (TCP/UDP)
```

**Why Network.framework?**
```swift
import Network  // Low-level TCP access

let connection = NWConnection(
    host: "127.0.0.1",
    port: 8888,
    using: .tcp  // Direct TCP control
)
```

**URLSession Doesn't Work For:**
- Custom protocols (not HTTP)
- Persistent bidirectional streams
- Low-latency requirements

**Lesson:** URLSession is for HTTP. Network.framework is for everything else.

### 5. Async Patterns in Swift

**The Recursive Receive Loop:**
```swift
private func receive() {
    connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) {
        [weak self] data, _, isComplete, error in

        if let data = data {
            self?.incomingBuffer += string
            self?.processBuffer()
        }

        if !isComplete {
            self?.receive()  // Recursive call
        }
    }
}
```

**Why Recursive?**
- TCP delivers data continuously
- Must keep reading until connection closes
- Callback-based (not blocking)

**Thread Safety:**
```swift
connection?.receive(...) { data, _, _, _ in
    // This runs on background queue

    DispatchQueue.main.async {
        // Update UI on main thread
        self.markets = decoded
    }
}
```

**Lesson:** Network callbacks run on background queues. Always dispatch to `main` for UI updates.

### 6. Price Conversion Architecture

**Three Representations:**

```
SERVER (Python)     NETWORK (JSON)      CLIENT (Swift)
Cents (int)    →    Number (60)    →    Cents (Double: 60.0)
                                              ↓
                                        UI (String: "$0.60")
```

**The Full Flow:**

```swift
// 1. Server → Client (Display)
let best_ask: Double = 60.0  // From JSON
let display = String(format: "$%.2f", best_ask / 100.0)  // "$0.60"

// 2. User Input → Server
let userInput = "0.50"  // TextField
let dollars = Double(userInput)!  // 0.50
let cents = Int(dollars * 100)  // 50
// Send: {"price": 50}

// 3. Server Processes
let price_in_cents = 50  // Python integer
```

**Why Three Layers?**
- **Server:** Integer precision for matching engine
- **Network:** JSON numbers (language-agnostic)
- **Client:** Doubles for flexibility, Strings for display

**Lesson:** Type conversion happens at boundaries. Each layer uses its natural representation.

## Implementation Patterns

### Pattern 1: State Machine for Connection

```swift
connection?.stateUpdateHandler = { state in
    switch state {
    case .preparing:  // DNS lookup, TCP handshake
    case .ready:      // Connected, ready to send/receive
    case .waiting(let error):  // Network unavailable, retry
    case .failed(let error):   // Connection failed, give up
    case .cancelled:  // Explicitly closed
    }
}
```

**Lesson:** TCP connections have clear state transitions. Handle each state appropriately.

### Pattern 2: Newline-Delimited JSON (NDJSON)

```
Request:  {"type":"get_markets"}\n
Response: {"status":"ok","markets":[...]}\n
```

**Advantages:**
- Each line is one complete message
- Easy to debug (cat, tail, grep work)
- Streaming friendly
- Language agnostic

**Lesson:** NDJSON is perfect for TCP-based APIs.

### Pattern 3: Type-Safe Codable Models

```swift
struct Market: Codable {
    let id: String
    let best_bid: Double?  // Cents from server
    let best_ask: Double?  // Cents from server
}

let decoder = JSONDecoder()
let response = try decoder.decode(GenericResponse.self, from: data)
```

**Why Optional (`Double?`)?**
- Market might not have bids/asks
- Compiler forces nil-checking
- Prevents runtime crashes

**Lesson:** Swift's type system prevents common bugs. Use Optionals for missing data.

## Testing Observations

**What Worked:**
- TCP connection established successfully
- Market data fetched and displayed
- Orders placed with correct price conversion
- Buffer management handled fragmented messages

**Backend Issues Found (Not Our Code):**
- Audit failure: Registry mismatch in matching engine
- Duplicate market IDs returned by server

**Lesson:** Client-side testing reveals server-side bugs. Good integration tests catch architectural issues.

## Mental Models

### Model 1: TCP as a Pipe

Think of TCP as a water pipe:
- Data flows continuously (stream)
- Chunks arrive at unpredictable intervals
- Need "buckets" (buffer) to collect complete "containers" (messages)
- Delimiter is like marking on containers

### Model 2: Price as an Integer with Scaling

```
Human View:     $0.50
Computer View:  50 cents (integer)
Scale Factor:   100 (cents per dollar)
```

Always store the integer, convert at display time.

### Model 3: Boundary Translation

```
Swift World          |  Boundary  |  Python World
-------------------- | ---------- | --------------------
String, Double       | JSON/TCP   | int, str, Decimal
Dollars for UI       |  <-->      | Cents for engine
UUIDs (String)       |  <-->      | CRC32 (int)
```

Each side uses its natural types. Translation happens at boundaries.

## Key Takeaways

1. **Financial Precision:** Use integers (cents) to avoid floating-point errors
2. **Protocol Choice:** TCP for custom protocols, HTTP for standard REST
3. **Framing:** Always solve the framing problem with TCP
4. **Type Safety:** Swift's Optionals and Codable prevent common bugs
5. **Async Patterns:** Recursive callbacks for continuous streams
6. **Documentation:** Comments should explain WHY, not just WHAT

## References

- Apple Network Framework: https://developer.apple.com/documentation/network
- NDJSON Spec: http://ndjson.org/
- Floating-Point Arithmetic: https://0.30000000000000004.com/
- Interface Layer: `logs/4-interface-pattern-adoption.md`

## Questions Answered

**Q: Why not WebSockets?**
A: WebSockets require HTTP upgrade handshake. For a local client, raw TCP is simpler.

**Q: Why not use Decimal on client?**
A: Server sends JSON numbers, which decode to Double. Converting at display is sufficient.

**Q: How to handle connection drops?**
A: Monitor `.failed` state, implement exponential backoff retry logic.

**Q: Why store prices as Double if server uses int?**
A: JSONDecoder converts numbers to Double. We document that these are cents, not dollars.

## Next Steps

1. Add connection timeout (5 seconds)
2. Implement retry logic for failed connections
3. Add WebSocket support for real-time market updates
4. Create PriceConverter utility for type safety
5. Write unit tests for price conversion logic

---

**Author's Note:** This was an excellent deep-dive into client-server architecture. The key insight: every boundary (Swift ↔ JSON ↔ Python) requires careful type translation. Document these boundaries clearly, and the rest becomes straightforward.
