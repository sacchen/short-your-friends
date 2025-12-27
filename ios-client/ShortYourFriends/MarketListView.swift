//
//  MarketListView.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/25/25.
//

import SwiftUI

struct MarketListView: View {
    @ObservedObject var client: NetworkClient
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Wallet Header
                // This section displays the balance received from the server
                HStack {
                    VStack(alignment: .leading) {
                        Text("Available Cash")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.gray)
                        
                        // Displays the balance string from NetworkClient
                        Text("$\(client.balance)")
                            .font(.system(size: 34, weight: .bold, design: .rounded))
                            .foregroundColor(.primary)
                    }
                    
                    Spacer()
                    
                    // Connection Status
                    HStack(spacing: 4) {
                        Circle()
                            .fill(client.isConnected ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(client.isConnected ? "Live" : "Offline")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(8)
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(12)
                }
                .padding()
                .background(Color(UIColor.systemBackground))
                
                Divider()
                
                // Main List
                List {
                    // Portfolio Section
                    // Only shows if you actually own shares
                    if !client.positions.isEmpty {
                        Section(header: Text("My Portfolio")) {
                            ForEach(client.positions) { position in
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(position.market_id)
                                            .font(.headline)
                                        Text(position.side)
                                            .font(.caption)
                                            .fontWeight(.bold)
                                            .foregroundColor(position.side == "LONG" ? .green : .red)
                                    }
                                    Spacer()
                                    Text("\(position.qty) shares")
                                        .font(.system(.body, design: .monospaced))
                                }
                            }
                        }
                    }
                    
                    // Markets Section
                    Section(header: Text("Active Markets")) {
                        ForEach(client.markets) { market in
                            NavigationLink(destination: MarketDetailView(market: market)
                                .environmentObject(client)) {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(market.name)
                                            .font(.headline)
                                        Text(market.id)
                                            .font(.caption)
                                            .foregroundColor(.gray)
                                    }
                                    
                                    Spacer()
                                    
                                    // Price Display: Spread
                                    VStack(alignment: .trailing) {
                                        if let bid = market.bestBid {
                                            Text(formatPrice(bid))
                                                .foregroundColor(.green)
                                        } else {
                                            Text("-").foregroundColor(.gray)
                                        }
                                        
                                        if let ask = market.bestAsk {
                                            Text(formatPrice(ask))
                                                .foregroundColor(.red)
                                        } else {
                                            Text("-").foregroundColor(.gray)
                                        }
                                    }
                                    .font(.system(.body, design: .monospaced))
                                }
                            }
                        }
                    }
                }
                .refreshable {
                    // Pull to refresh
                    client.fetchMarkets()
                }
            }
            .navigationTitle("Exchange")
            .navigationBarTitleDisplayMode(.inline)
            
            // Toolbar Block
            .toolbar {
                // Mint / Faucet Button
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: {
                        // Send a fake "walk" to generate cash for the CURRENT user
                        // Mint $10.00 (1000 steps)
                        client.send(request: [
                            "type": "proof_of_walk",
                            "user_id": client.userId,
                            "steps": 1000
                        ])
                        
                        // Refresh balance after a brief delay
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                            client.fetchMarkets()
                        }
                    }) {
                        Image(systemName: "banknote")
                    }
                }
                
                // User Switcher
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        // Toggle Logic
                        client.userId = (client.userId == "test_user_1") ? "test_user_2" : "test_user_1"
                        
                        // Fetch new user's balance
                        client.fetchMarkets()
                    }) {
                        HStack {
                            Text(client.userId == "test_user_1" ? "User 1" : "User 2")
                                .font(.caption)
                                .bold()
                            Image(systemName: "person.2.circle.fill")
                        }
                    }
                }
            }
            
            .onAppear {
                // Autoconnect on load
                if !client.isConnected {
                    client.connect()
                }
            }
        }
    }

    func formatPrice(_ cents: Double?) -> String {
        guard let c = cents else { return "-" }
        return String(format: "$%.2f", c / 100.0)
    }
}