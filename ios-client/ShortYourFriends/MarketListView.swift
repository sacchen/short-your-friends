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