//
//  NetworkClient.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/24/25.
//
import Foundation
import Network
import Combine

// 1. Define the shape of a Response (matches Python JSON)
struct ServerResponse: Decodable {
    let status: String
    let message: String?
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
    
    // Buffer State
    // Accumulate incoming bytes until /n
    private var incomingBuffer: String = ""

    func connect(host: String = "127.0.0.1", port: UInt16 = 8888) {
        let hostEndpoint = NWEndpoint.Host(host)
        let portEndpoint = NWEndpoint.Port(rawValue: port)!
        
        // Create the connection
        connection = NWConnection(host: hostEndpoint, port: portEndpoint, using: .tcp)
        
        // Handle state changes (did we disconnect?)
        connection?.stateUpdateHandler = { state in
            DispatchQueue.main.async {
                switch state {
                case .ready:
                    self.isConnected = true
                    self.log = "Connected to \(host)"
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
    
    // Generic Send
    // Send JSON Dictionary
    func send(request: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: request),
              var string = String(data: data, encoding: .utf8) else { return }
        
        // Protocol Delimiter: Add newline so Python knows message is done
        string += "\n"
        
        let content = string.data(using: .utf8)
        
        connection?.send(content: content, completion: .contentProcessed({ error in
            if let error = error {
                print("Send error: \(error)")
            }
        }))
    }
    
    // Receive Loop
    // Listen for response
    private func receive() {
        // Read until newline (matching python's readuntil(b"\n"))
        // Read as much as possible, up to 64KB.
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, isComplete, error in
            if let data = data, let string = String(data: data, encoding: .utf8) {
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
        // While: newline in buffer, we have complete message.
        while let range = incomingBuffer.range(of: "\n") {
            // Extract message up to newline
            let message = String(incomingBuffer[..<range.lowerBound])
            
            // Remove that message and newline
            incomingBuffer.removeSubrange(..<range.upperBound)
            
            // Handle complete JSON string
            handleMessage(message)
        }
    }
    
    // Message Router
    private func handleMessage(_ jsonString: String) {
        guard let data = jsonString.data(using: .utf8) else { return }
        
        // Decode on main thread so UI updates instantly
        DispatchQueue.main.async {
            // Decode Wrapper (GenericResponse), not Array
            if let response = try? JSONDecoder().decode(GenericResponse.self, from: data) {
                
                // If response contains list of markets, update state
                if let receivedMarkets = response.markets {
                    self.markets = receivedMarkets
                    self.log = "Updated \(receivedMarkets.count) markets"
                    return
                }
                
                // If just status update (eg placing order)
                if let status = response.status {
                    self.log = "Server: \(status)"
                    return
                }
            }
            
            // Fallback
            self.log = "Unknown Msg: \(jsonString)"
            
            // Attempt decode as a List of Markets ("Get Markets" response)
            // Check "type" field first in the future
            if let marketList = try? JSONDecoder().decode([Market].self, from: data) {
                self.markets = marketList
                self.log = "Updated \(marketList.count) markets"
                return
            }
            
            // If not a market list, log for now
            self.log = "Unknown Msg: \(jsonString)"
        }
    }
    
}
