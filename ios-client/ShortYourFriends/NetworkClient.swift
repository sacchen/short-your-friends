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
    
    // These @Published properties require the 'Combine' import to work
    @Published var isConnected: Bool = false
    @Published var lastMessage: String = "Ready"

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
                    self.lastMessage = "Connected to \(host)"
                case .failed(let error):
                    self.isConnected = false
                    self.lastMessage = "Failed: \(error)"
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
    
    // Send JSON Dictionary
    func send(request: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: request),
              var string = String(data: data, encoding: .utf8) else { return }
        
        // IMPORTANT: Add the newline so Python knows the message is done
        string += "\n"
        
        let content = string.data(using: .utf8)
        
        connection?.send(content: content, completion: .contentProcessed({ error in
            if let error = error {
                print("Send error: \(error)")
            }
        }))
    }
    
    // Listen for response
    private func receive() {
        // Read until newline (matching python's readuntil(b"\n"))
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, isComplete, error in
            if let data = data, let message = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async {
                    self.lastMessage = "Received: \(message)"
                }
            }
            
            if isComplete || error != nil {
                self.isConnected = false
            } else {
                // Keep listening (recursive loop)
                self.receive()
            }
        }
    }
}
