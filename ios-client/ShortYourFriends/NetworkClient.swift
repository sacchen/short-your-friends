//
//  NetworkClient.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/24/25.
//

import Foundation
import Network
import Combine

// UNIFIED RESPONSE STRUCT
// This matches everything the server sends (Markets, Balance, or Status)
struct GenericResponse: Decodable {
    let status: String?      // Optional: not every response has status
    let message: String?
    let type: String?
    
    // Data Payloads (Optional, because not every message has them)
    let markets: [Market]?
    let available: String?
    let locked: String?
    let total_equity: String?
}

class NetworkClient: ObservableObject {
    private var connection: NWConnection?
    
    // App State
    @Published var isConnected: Bool = false
    @Published var markets: [Market] = []
    @Published var log: String = "Ready"    // Renamed from lastMessage
    @Published var balance: String = "0.00"
    
    // Buffer State
    // Accumulate incoming bytes until \n
    private var incomingBuffer: String = ""

    func connect(host: String = "127.0.0.1", port: UInt16 = 8888) {
        let hostEndpoint: NWEndpoint.Host = NWEndpoint.Host(host)
        let portEndpoint: NWEndpoint.Port = NWEndpoint.Port(rawValue: port)!
        
        // Create the connection
        connection = NWConnection(host: hostEndpoint, port: portEndpoint, using: .tcp)
        
        // Handle state changes (did we disconnect?)
        connection?.stateUpdateHandler = { state: NWConnection.State in
            DispatchQueue.main.async {
                switch state {
                case .ready:
                    self.isConnected = true
                    self.log = "Connected to \(host)"
                    // Auto-fetch on connect
                    self.fetchMarkets()
                case .failed(let error):
                    self.isConnected = false
                    self.log = "Failed: \(error)"
                case .cancelled:
                    self.isConnected = false
                default:
                    break
                }
            }
        }
        
        // Start the connection
        connection?.start(queue: .global())
        
        // Start listening for incoming data immediately
        receive()
    }
    
    // MARK: - Sending
    
    // Send JSON Dictionary
    func send(request: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: request),
              var string = String(data: data, encoding: .utf8) else { return }
        
        // Protocol Delimiter: Add newline so Python knows message is done
        string += "\n"
        
        let content = string.data(using: .utf8)
        
        connection?.send(content: content, completion: .contentProcessed({ error: NWError? in
            if let error = error {
                print("Send error: \(error)")
            }
        }))
    }
    
    // MARK: - Receiving
    
    // Receive Loop - Listen for response
    private func receive() {
        // Read until newline (matching python's readuntil(b"\n"))
        // Read as much as possible, up to 64KB
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data: Data?, _: NWConnection.ContentContext?, isComplete, error in
            if let data: Data = data, let string: String = String(data: data, encoding: .utf8) {
                // Append new data to buffer
                self.incomingBuffer += string
                
                // Process buffer
                self.processBuffer()
            }
            
            if isComplete || error != nil {
                DispatchQueue.main.async { self.isConnected = false }
            } else {
                // Keep listening (recursive loop)
                self.receive()
            }
        }
    }
    
    // Buffer Processing / Parser
    private func processBuffer() {
        // While: newline in buffer, we have complete message
        while let range: Range<String.Index> = incomingBuffer.range(of: "\n") {
            // Extract message up to newline
            let message = String(incomingBuffer[..<range.lowerBound])
            
            // Remove that message and newline
            incomingBuffer.removeSubrange(..<range.upperBound)
            
            // Handle complete JSON string
            handleMessage(message)
        }
    }
    
    // MARK: - Message Router
    
    private func handleMessage(_ jsonString: String) {
        guard let data: Data = jsonString.data(using: .utf8) else { return }
        
        // Decode on main thread so UI updates instantly
        DispatchQueue.main.async {
            do {
                // Decode Wrapper (GenericResponse) - unified format from server
                let response = try JSONDecoder().decode(GenericResponse.self, from: data)
                
                // 1. Handle Markets Update
                // If response contains list of markets, update state
                if let receivedMarkets = response.markets {
                    self.markets = receivedMarkets
                    self.log = "Updated \(receivedMarkets.count) markets"
                }
                
                // 2. Handle Balance Update
                if let av = response.available {
                    self.balance = av
                }
                
                // 3. Handle Status/Errors
                // Only show explicit errors to user
                if let status = response.status, status == "error" {
                    let msg = response.message ?? "Unknown error"
                    self.log = "Error: \(msg)"
                }
                
            } catch {
                // If decode fails, log for debugging
                print("JSON Decode Error: \(error)")
                self.log = "Decode Error: \(jsonString)"
            }
        }
    }
    
    // MARK: - API Methods
    
    func fetchMarkets() {
        // Send {"type": "get_markets"}
        send(request: ["type": "get_markets"])
        
        // Fetch balance - use String "test_user_1" to match your funded account
        send(request: ["type": "balance", "user_id": "test_user_1"])
    }
    
    func placeOrder(marketId: String, side: String, price: Double, quantity: Int) {
        // Convert Dollars to Cents
        let priceInCents = Int(price * 100)
        
        // Construct Payload
        let payload: [String: Any] = [
            "type": "place_order",
            "market_id": marketId,
            "user_id": "test_user_1",  // Use String ID to match server
            "side": side,
            "price": priceInCents,
            "qty": quantity,
            "id": Int.random(in: 1000...99999)
        ]
        
        // Send
        send(request: payload)
        
        // Optimistic Refresh - wait a bit then refetch
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            self.fetchMarkets()
        }
    }
}