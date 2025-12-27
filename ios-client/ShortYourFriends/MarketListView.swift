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
            VStack {
                // Connection Status Strip
                HStack {
                    Circle()
                        .fill(client.isConnected ? Color.green : Color.red)
                        .frame(width: 10, height: 10)
                    Text(client.log)
                        .font(.caption)
                        .foregroundColor(.gray)
                    Spacer()
                }
                .padding()
                
                // Market List
                List(client.markets) { market in
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
                                    Text("No Bids").foregroundColor(.gray)
                                }
                                
                                if let ask = market.bestAsk {
                                    Text(formatPrice(ask))
                                        .foregroundColor(.red)
                                } else {
                                    Text("No Asks").foregroundColor(.gray)
                                }
                            }
                            .font(.system(.body, design: .monospaced))
                        }
                    }
                }
                .refreshable {
                    // Pull to refresh
                    client.send(request: ["type": "get_markets"])
                }
            }
            .navigationTitle("Markets")

            // Toolbar Block
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: {
                        // Send a fake "walk" to generate cash for the CURRENT user
                        client.send(request: [
                            "type": "proof_of_walk",
                            "user_id": client.userId, // Uses the active user
                            "steps": 1000  // Mints $1.00 (assuming 10 steps = 1 cent)
                        ])
                        
                        // Refresh balance after a brief delay
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                            client.fetchMarkets()
                        }
                    }) {
                        Image(systemName: "banknote")
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        // Toggle Logic
                        client.userId = (client.userId == "test_user_1") ? "test_user_2" : "test_user_1"

                        // Fetch new user's balance
                        client.fetchMarkets()
                    })
                    {
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
                // Autoconnect and fetch on load
                if !client.isConnected {
                    client.connect()
                }
                // Give connection a split second, then fetch
                // TODO: Send automatically on connect in the future
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    client.send(request: ["type": "get_markets"])
                }
            }
        }
    }

    func formatPrice(_ cents: Double?) -> String {
        guard let c = cents else { return "-" }
        return String(format: "$%.2f", c / 100.0)
    }
}