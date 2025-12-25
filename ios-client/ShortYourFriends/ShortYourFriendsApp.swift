//
//  ShortYourFriendsApp.swift
//  ShortYourFriends
//
//  Created by Samuel Chen on 12/24/25.
//

import SwiftUI

@main
struct ShortYourFriendsApp: App {
    // Create client
    @StateObject var client = NetworkClient()
    
    var body: some Scene {
        WindowGroup {
            // ContentView()
            MarketListView(client: client)
        }
    }
}
