//
//  ContentView.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/24/25.
//

import SwiftUI

struct ContentView: View {
    @StateObject var client = NetworkClient()
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .imageScale(.large)
                .foregroundStyle(.tint)
            
            Text("Short Your Friends")
                .font(.largeTitle)
                .bold()
            
            // Status Indicator
            HStack {
                Circle()
                    .fill(client.isConnected ? Color.green : Color.red)
                    .frame(width: 10, height: 10)
                Text(client.isConnected ? "Online" : "Offline")
            }
            
            Text(client.lastMessage)
                .font(.caption)
                .foregroundStyle(.gray)
                .padding()
                .background(Color.black.opacity(0.05))
                .cornerRadius(8)
            
            if !client.isConnected {
                Button("Connect to Server") {
                    // Make sure Python server is running!
                    client.connect()
                }
                .buttonStyle(.borderedProminent)
            } else {
                VStack {
                    Button("Check Balance") {
                        client.send(request: [
                            "type": "balance",
                            "user_id": "ios_user"
                        ])
                    }
                    
                    Button("Mint 100 Credits") {
                        client.send(request: [
                            "type": "proof_of_walk",
                            "user_id": "ios_user",
                            "steps": 10000
                        ])
                    }
                    .tint(.green)
                }
                .buttonStyle(.bordered)
            }
        }
        .padding()
    }
}
