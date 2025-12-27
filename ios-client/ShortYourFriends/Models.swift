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

// // Full market state
// struct Market: Codable, Identifiable {
//     let id: String      // "alice_sleep"
//     let name: String    // "Alice Sleep Schedule"
    
//     // Arrays of orders. Optional: Server might not send these in list view
//     let bids: [OrderLevel]?
//     let asks: [OrderLevel]?
    
//     // Stored properties.
//     // Captures the "best_bid" and "best_ask" values the server sends.
//     // We use Double here because UI expects it,
//     // JSONDecoder handles Int->Double conversion.
//     let bestBid: Double?
//     let bestAsk: Double?
    
//     // Map JSON keys (snake_case) to Swift properties (camelCase)
//         enum CodingKeys: String, CodingKey {
//             case id
//             case name
//             case bids
//             case asks
//             case bestBid = "best_bid"
//             case bestAsk = "best_ask"
//         }
// }

// // Wrapper for response logic
// // To detect what server sent us
// struct GenericResponse: Decodable {
//     let status: String?
//     let message: String?
//     let type: String?       // TODO: Add to Python responses later
//     let markets: [Market]?
//     let balance: Double?
// }
