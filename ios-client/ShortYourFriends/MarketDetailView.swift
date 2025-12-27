//
//  MarketDetailView.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/26/25.
//

import SwiftUI

struct MarketDetailView: View {
    // Connect to the shared NetworkClient
    @EnvironmentObject var api: NetworkClient
    let market: Market
    
    @State private var priceString: String = ""
    @State private var quantityString: String = "1"
    @State private var feedbackMsg: String = ""
    
    var body: some View {
        VStack(spacing: 20) {
            // MARK: - Header Stats
            HStack(spacing: 40) {
                // Bid Column
                VStack {
                    Text("Best Bid")
                        .font(.caption)
                        .foregroundColor(.gray)
                    Text(formatPrice(market.bestBid))
                        .font(.title)
                        .bold()
                        .foregroundColor(.green)
                }
                
                // Ask Column
                VStack {
                    Text("Best Ask")
                        .font(.caption)
                        .foregroundColor(.gray)
                    Text(formatPrice(market.bestAsk))
                        .font(.title)
                        .bold()
                        .foregroundColor(.red)
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
            
            // MARK: - Order Form
            VStack(alignment: .leading, spacing: 15) {
                Text("Place Limit Order")
                    .font(.headline)
                
                // Price Input
                HStack {
                    Text("Price ($)")
                        .frame(width: 80, alignment: .leading)
                    TextField("0.00", text: $priceString)
                        .keyboardType(.decimalPad)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                
                // Quantity Input
                HStack {
                    Text("Quantity")
                        .frame(width: 80, alignment: .leading)
                    TextField("1", text: $quantityString)
                        .keyboardType(.numberPad)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
            }
            .padding()
            
            // MARK: - Action Buttons
            HStack(spacing: 15) {
                // BUY BUTTON
                Button(action: { submitOrder(side: "buy") }) {
                    Text("BUY")
                        .bold()
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(10)
                }
                
                // SELL BUTTON
                Button(action: { submitOrder(side: "sell") }) {
                    Text("SELL")
                        .bold()
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(10)
                }
            }
            .padding(.horizontal)
            
            // Feedback Text
            if !feedbackMsg.isEmpty {
                Text(feedbackMsg)
                    .font(.caption)
                    .foregroundColor(.gray)
                    .padding(.top)
            }
            
            Spacer()
        }
        .padding()
        .navigationTitle(market.name)
        .onAppear {
            // Auto-fill price: If buying, suggest the Ask price (market buy)
            if let ask = market.bestAsk {
                priceString = String(format: "%.2f", ask / 100.0)
            }
        }
    }
    
    // MARK: - Helpers
    
    // Helper: Convert "41" (cents) -> "$0.41"
    func formatPrice(_ cents: Double?) -> String {
        guard let c = cents else { return "—" }
        return String(format: "$%.2f", c / 100.0)
    }
    
    func submitOrder(side: String) {
        // Simple input validation
        guard let price = Double(priceString),
              let qty = Int(quantityString) else {
            feedbackMsg = "Invalid input"
            return
        }
        
        // Call the API
        api.placeOrder(
            marketId: market.id,
            side: side,
            price: price,
            quantity: qty
        )
        
        feedbackMsg = "Sent \(side.uppercased()) for \(qty) @ $\(price)"
        
        // Haptic feedback (Vibrate)
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)
    }
}