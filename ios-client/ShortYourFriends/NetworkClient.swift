//
//  NetworkClient.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/24/25.
//

import Foundation
import Network
import Combine

struct Market: Identifiable, Codable, Hashable {
    let id: String
    let name: String
    // Server sends these as snake_case Ints (cents)
    let best_bid: Double?
    let best_ask: Double?
    
    // Computed properties for cleaner SwiftUI access
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

    func connect(host: String = "127.0.0.1", port: UInt16 = 8888) {
        let hostEndpoint = NWEndpoint.Host(host)
        guard let portEndpoint = NWEndpoint.Port(rawValue: port) else { return }
        
        connection = NWConnection(host: hostEndpoint, port: portEndpoint, using: .tcp)
        
        connection?.stateUpdateHandler = { state in
            DispatchQueue.main.async {
                switch state {
                case .ready:
                    self.isConnected = true
                    self.log = "Connected to \(host)"
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
        
        connection?.start(queue: .global())
        receive()
    }
    
    // MARK: - Sending
    
    func send(request: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: request),
              var string = String(data: data, encoding: .utf8) else { return }
        
        string += "\n"
        let content = string.data(using: .utf8)
        
        connection?.send(content: content, completion: .contentProcessed({ error in
            if let error = error {
                print("Send error: \(error)")
            }
        }))
    }
    
    // MARK: - Receiving
    
    private func receive() {
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            guard let self = self else { return }
            
            if let data = data, let string = String(data: data, encoding: .utf8) {
                self.incomingBuffer += string
                self.processBuffer()
            }
            
            if isComplete || error != nil {
                DispatchQueue.main.async { self.isConnected = false }
            } else {
                self.receive()
            }
        }
    }
    
    // Buffer Parser
    private func processBuffer() {
        while let range = self.incomingBuffer.range(of: "\n") {
            let message = String(self.incomingBuffer[..<range.lowerBound])
            self.incomingBuffer.removeSubrange(..<range.upperBound)
            self.handleMessage(message)
        }
    }
    
    // Message Router
    private func handleMessage(_ jsonString: String) {
        guard let data = jsonString.data(using: .utf8) else { return }
        
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
    
    func placeOrder(marketId: String, side: String, price: Double, quantity: Int) {
        let priceInCents = Int(price * 100)
        let payload: [String: Any] = [
            "type": "place_order",
            "market_id": marketId,
            "user_id": self.userId,
            "side": side,
            "price": priceInCents,
            "qty": quantity,
            "id": Int.random(in: 1000...99999)
        ]
        self.send(request: payload)
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            self.fetchMarkets()
        }
    }
}
