//
//  NetworkClient.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/24/25.
//

import Foundation
import Network
import Combine

// MARK: - Architecture Notes
//
// PRICE REPRESENTATION ACROSS BOUNDARIES:
//
// 1. Server Storage (Python):
//    - Engine uses CENTS as integers (e.g., 60 = $0.60)
//    - Reason: Avoid floating-point precision errors in matching
//    - Example: 0.1 + 0.2 ≠ 0.3 in floating point!
//
// 2. Network Protocol (JSON):
//    - Server sends: {"best_ask": 60} (cents as number)
//    - Swift decodes as Double: best_ask = 60.0
//    - Note: JSON numbers become Double in Swift Codable
//
// 3. Client UI (SwiftUI):
//    - Display to user: "0.60" (dollars as string)
//    - TextField input: user enters "0.50" (thinks in dollars)
//    - Conversion: dollars * 100 = cents before sending
//
// FLOW EXAMPLE (Buy order at $0.50):
// - User inputs: "0.50" (String in TextField)
// - Parse to Double: 0.50
// - Convert to cents: Int(0.50 * 100) = 50
// - Send to server: {"price": 50}
// - Server processes: 50 cents = valid price
//
// NETWORK PROTOCOL:
//
// - Transport: Raw TCP (not HTTP!)
// - Format: Newline-delimited JSON
// - Framing: Each message ends with '\n'
//
// Why TCP instead of HTTP?
// - Lower latency (no HTTP header overhead)
// - Persistent connection (no reconnect per request)
// - Custom protocol (streaming updates possible)
//
// Why newline-delimited?
// - TCP is a STREAM protocol (not message-based)
// - Need delimiter to know where one message ends
// - '\n' is simple and JSON-safe (no '\n' inside JSON)
//
// Example message exchange:
//   Client → Server: {"type":"get_markets"}\n
//   Server → Client: {"status":"ok","markets":[...]}\n

struct Market: Identifiable, Codable, Hashable {
    let id: String  // Format: "alice_480" (username_threshold_minutes)
    let name: String

    // IMPORTANT: These are in CENTS, not dollars!
    // Server sends: {"best_bid": 40, "best_ask": 60}
    // Meaning: $0.40 bid, $0.60 ask
    // Type is Double because JSONDecoder converts JSON numbers to Double
    let best_bid: Double?  // Best bid price in cents (e.g., 40 = $0.40)
    let best_ask: Double?  // Best ask price in cents (e.g., 60 = $0.60)

    // Computed properties: Convert cents to dollars for UI display
    var bestBid: Double? { return best_bid }
    var bestAsk: Double? { return best_ask }
}

struct Position: Identifiable, Decodable {
    var id: String { market_id} // conform to Identifiable
    let market_id: String
    let side: String // "LONG" or "SHORT"
    let qty: Int
    let average_price: Double
}

struct GenericResponse: Decodable {
    let status: String?
    let message: String?
    let type: String?
    
    // Data Payloads
    let markets: [Market]?
    let available: String?
    let locked: String?
    let total_equity: String?
    let positions: [Position]?
}

class NetworkClient: ObservableObject {
    private var connection: NWConnection?
    
    // App State
    @Published var isConnected: Bool = false
    @Published var markets: [Market] = []
    @Published var log: String = "Ready"
    @Published var balance: String = "0.00"

    @Published var positions: [Position] = []

    // Users
    @Published var userId: String = "test_user_1"
    
    // Buffer State
    private var incomingBuffer: String = ""

    // MARK: - Connection Management
    //
    // Uses Apple's Network framework (not URLSession) because:
    // 1. URLSession is for HTTP/HTTPS only
    // 2. Network framework gives low-level TCP/UDP access
    // 3. Better control over connection lifecycle
    //
    func connect(host: String = "127.0.0.1", port: UInt16 = 8888) {
        let hostEndpoint = NWEndpoint.Host(host)
        guard let portEndpoint = NWEndpoint.Port(rawValue: port) else { return }

        // Create TCP connection
        // .tcp parameter: uses TCP protocol (reliable, ordered delivery)
        connection = NWConnection(host: hostEndpoint, port: portEndpoint, using: .tcp)

        // State handler: Monitor connection lifecycle
        // States: .preparing → .ready → .failed/.cancelled
        connection?.stateUpdateHandler = { state in
            DispatchQueue.main.async {  // Update UI on main thread
                switch state {
                case .ready:
                    // TCP handshake complete, can send/receive
                    self.isConnected = true
                    self.log = "Connected to \(host)"
                    self.fetchMarkets()  // Auto-fetch on connect
                case .failed(let error):
                    // Connection failed (server down, network issue)
                    self.isConnected = false
                    self.log = "Failed: \(error)"
                case .cancelled:
                    // Connection closed (by us or server)
                    self.isConnected = false
                default:
                    break
                }
            }
        }

        // Start connection on background queue
        // .global(): System-managed concurrent queue
        connection?.start(queue: .global())

        // Start receiving data
        receive()
    }
    
    // MARK: - Sending Data
    //
    // Convert Swift dictionary to JSON string, append '\n', send over TCP
    func send(request: [String: Any]) {
        // Serialize dictionary to JSON bytes
        guard let data = try? JSONSerialization.data(withJSONObject: request),
              var string = String(data: data, encoding: .utf8) else { return }

        // Add newline delimiter (critical for server framing)
        string += "\n"
        let content = string.data(using: .utf8)

        // Send data over TCP connection
        connection?.send(content: content, completion: .contentProcessed({ error in
            if let error = error {
                print("Send error: \(error)")
            }
        }))
    }
    
    // MARK: - Receiving Data
    //
    // THE FRAMING PROBLEM:
    // TCP delivers a stream of bytes, not discrete messages.
    // Data can arrive in chunks of any size:
    //   Chunk 1: {"type":"get_mar
    //   Chunk 2: kets"}\n{"type":"bal
    //   Chunk 3: ance"}\n
    //
    // SOLUTION: Buffer + Delimiter
    // 1. Accumulate all received bytes in a buffer
    // 2. Scan for '\n' delimiter
    // 3. Extract complete messages, process them
    // 4. Keep incomplete data in buffer for next chunk

    private func receive() {
        // Request data from connection
        // minimumIncompleteLength: 1 = read at least 1 byte
        // maximumLength: 65536 = max 64KB per read
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            guard let self = self else { return }

            if let data = data, let string = String(data: data, encoding: .utf8) {
                // Append new data to buffer
                self.incomingBuffer += string
                // Try to extract complete messages
                self.processBuffer()
            }

            if isComplete || error != nil {
                // Connection closed
                DispatchQueue.main.async { self.isConnected = false }
            } else {
                // Keep reading (recursive call)
                self.receive()
            }
        }
    }

    // Extract complete messages from buffer
    private func processBuffer() {
        // Loop: Handle multiple messages in one chunk
        while let range = self.incomingBuffer.range(of: "\n") {
            // Extract message (everything before '\n')
            let message = String(self.incomingBuffer[..<range.lowerBound])
            // Remove message + delimiter from buffer
            self.incomingBuffer.removeSubrange(..<range.upperBound)
            // Process the message
            self.handleMessage(message)
        }
        // Any remaining data stays in buffer for next receive()
    }
    
    // Message Router
    private func handleMessage(_ jsonString: String) {
        guard let data = jsonString.data(using: .utf8) else { return }
        
        // Debug: see what Server sends
        print("[+] Received: \(jsonString)")
        
        DispatchQueue.main.async {
            do {
                let response = try JSONDecoder().decode(GenericResponse.self, from: data)
                
                if let receivedMarkets = response.markets {
                    self.markets = receivedMarkets
                    self.log = "Updated \(receivedMarkets.count) markets"
                }
                
                if let av = response.available {
                    self.balance = av
                }
                
                if let status = response.status, status == "error" {
                    let msg = response.message ?? "Unknown error"
                    self.log = "Error: \(msg)"
                }
                
            } catch {
                print("JSON Decode Error: \(error)")
                self.log = "Decode Error"
            }
        }
    }
    
    // MARK: - API Methods

    func fetchMarkets() {
        self.send(request: ["type": "get_markets"])
        self.send(request: ["type": "balance", "user_id": self.userId])
    }

    // MARK: - Place Order
    //
    // Takes UI-friendly parameters (price in dollars) and converts to
    // server-expected format (price in cents).
    //
    // Parameters:
    //   - price: Dollar amount (e.g., 0.50 for 50 cents)
    //   - quantity: Number of contracts
    //
    // Network message sent:
    //   {"type": "place_order", "price": 50, "qty": 1, ...}
    func placeOrder(marketId: String, side: String, price: Double, quantity: Int) {
        // Convert dollars to cents for server
        // Example: 0.50 * 100 = 50.0 → Int cast → 50
        let priceInCents = Int(price * 100)

        let payload: [String: Any] = [
            "type": "place_order",
            "market_id": marketId,      // Format: "alice_480"
            "user_id": self.userId,
            "side": side,               // "buy" or "sell"
            "price": priceInCents,      // Cents (e.g., 50 = $0.50)
            "qty": quantity,
            "id": Int.random(in: 1000...99999)  // Random order ID
        ]
        self.send(request: payload)

        // Refresh data after slight delay to see updates
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            self.fetchMarkets()
        }
    }
}
