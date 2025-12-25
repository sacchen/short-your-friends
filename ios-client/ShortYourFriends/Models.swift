//
//  Models.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/25/25.
//
import Foundation

// One limit order (Bid/Ask)
struct OrderLevel: Codable, Identifiable {
    var id: Double { price }    // Price as unique ID for UI
    let price: Double
    let quantity: Int
}

// Full market state
struct Market: Codable, Identifiable {
    let id: String      // "alice_sleep"
    let name: String    // "Alice Sleep Schedule"
    
    // Arrays of orders. optional for empty markets
    let bids: [OrderLevel]?
    let asks: [OrderLevel]?
    
    // Helper for UI to show a Spread
    var bestBid: Double? { bids?.first?.price }
    var bestAsk: Double? { asks?.first?.price }
}

// Wrapper for response logic
// To detect what server sent us
struct GenericResponse: Decodable {
    let status: String?
    let type: String?       // TODO: Add to Python responses later
    let markets: [Market]?
    let balance: Double?
}
