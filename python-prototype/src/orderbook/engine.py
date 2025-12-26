from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .book import OrderBook
from .trade import Trade
from .types import PriceLevel

# Market identifier: (target_user_id, threshold_minutes)
type MarketId = Tuple[int, int]


@dataclass
class MatchingEngine:
    """
    Multi-market matching engine.
    Each market is an independent OrderBook.
    """

    _markets: Dict[MarketId, OrderBook] = field(default_factory=dict)
    _market_names: Dict[MarketId, str] = field(default_factory=dict)

    def get_or_create_market(self, market_id: MarketId) -> OrderBook:
        if market_id not in self._markets:
            self._markets[market_id] = OrderBook()
        return self._markets[market_id]

    def create_market(self, market_id: MarketId, name: str) -> None:
        """
        Creates a market with a display name.
        Is called by Seed Data in server.
        """
        self.get_or_create_market(market_id)
        self._market_names[market_id] = name

    def process_order(
        self,
        market_id: MarketId,
        side: str,
        price: int,
        quantity: int,
        order_id: int,
        user_id: int,
    ) -> list[Trade]:
        book = self.get_or_create_market(market_id)
        return book.process_order(side, price, quantity, order_id, user_id)

    def settle_markets_for_user(
        self,
        target_user_id: int,
        actual_screentime_minutes: int,
    ) -> list[Trade]:
        """
        Settle all markets for a given target_user_id based on actual screentime.
        Returns all synthetic trades from settlement.
        """
        all_trades: list[Trade] = []

        for market_id in list(self._markets.keys()):
            if market_id[0] == target_user_id:  # Same target user
                threshold = market_id[1]
                terminal_price = 1 if actual_screentime_minutes >= threshold else 0
                trades = self._markets[market_id].settle_market(terminal_price)
                all_trades.extend(trades)

        return all_trades

    def get_market_snapshot(self, market_id: MarketId) -> dict[str, list[PriceLevel]]:
        """Get snapshot for a specific market"""
        if market_id not in self._markets:
            return {"bids": [], "asks": []}
        return self._markets[market_id].snapshot()

    def get_active_markets(self) -> list[dict[str, Any]]:
        """
        Returns list of active markets for API.
        """
        market_list = []
        for market_id, book in self._markets.items():
            # Use max() for best bid and min() for best ask
            # book._bids is a dict {price: OrderNode}, so we look at .keys()

            best_bid = max(book._bids.keys()) if book._bids else None
            best_ask = min(book._asks.keys()) if book._asks else None

            target_user, minutes = market_id

            # Use stored name or fallback to default string
            display_name = self._market_names.get(
                market_id, f"{target_user} > {minutes}m"
            )

            market_list.append(
                {
                    "id": f"{target_user}_{minutes}",  # Unique ID for SwiftUI
                    "name": display_name,
                    "target_user": target_user,
                    "threshold_minutes": minutes,
                    "best_bid": str(best_bid) if best_bid is not None else None,
                    "best_ask": str(best_ask) if best_ask is not None else None,
                    "volume": 0,  # TODO: track volume
                }
            )
        return market_list

    # TODO: add get_market_details() that returns graph data/history

    def dump_state(self) -> dict:
        """
        Serializes all markets and their order books to JSON.
        Structure:
        {
            "market_key_str": {
                "bids": [ {order_dict}, ... ],
                "asks": [ {order_dict}, ... ]
            }
        }
        """
        markets_data = {}

        # Helper
        def serialize_orders(orders_map, side_label):
            serialized_list = []

            # orders_map is {price: OrderNode}
            # We use .values() to get the OrderNodes (not the price keys)
            for order_list in orders_map.values():
                curr = getattr(order_list, "head", None)

                # Walk the linked list if there are multiple orders at this price
                while curr:
                    serialized_list.append(
                        {
                            "id": curr.order_id,
                            "user_id": curr.user_id,
                            "price": int(curr.price),
                            "qty": curr.quantity,
                            "side": side_label,
                            # Safe check for timestamp
                            "timestamp": getattr(curr, "timestamp", 0),
                        }
                    )
                    # Move to next order in linked list (safe check)
                    curr = getattr(curr, "next", None)
            return serialized_list

        for market_id, book in self._markets.items():
            # Composite key needs to be a string for JSON
            # key is tuple before converting to string
            # key format: "user_id:minutes"
            markets_data[market_id] = {
                "name": self._market_names.get(market_id, "Unknown Market"),
                "bids": serialize_orders(book._bids, "buy"),
                "asks": serialize_orders(book._asks, "sell"),
            }

        return {"markets": markets_data}

    def load_state(self, state):
        """
        Restores market state from JSON dictionary.
        """
        if "markets" not in state:
            return

        self._markets.clear()
        self._market_names.clear()

        for key_str, market_data in state["markets"].items():
            try:
                # Parse key: Handle the "alice,480" format from server.py
                if "," in key_str:
                    target_user, minutes_str = key_str.split(",")
                elif ":" in key_str:
                    target_user, minutes_str = key_str.split(":")
                else:
                    # If it's just a raw tuple string or weird format, skip or log
                    print(f"[!] Skipping invalid market key: {key_str}")
                    continue

                # Reconstruct Tuple ID
                market_id = (target_user, int(minutes_str))

                # Read name from JSON, or fallback to default
                market_name = market_data.get("name", f"{target_user} > {minutes_str}m")

                # Create market
                self.create_market(market_id, market_name)
                book = self._markets[market_id]

                # Helper to restore orders
                def restore_orders(order_list_data, side):
                    for o_data in order_list_data:
                        # Pass arguments explicitly. Previously was Node object
                        book.add_order(
                            side=side,
                            price=o_data["price"],
                            quantity=o_data["qty"],
                            order_id=o_data["id"],
                            user_id=o_data["user_id"],
                        )
                        # Create node
                        # node = OrderNode(
                        #     order_id=o_data["id"],
                        #     user_id=o_data["user_id"],
                        #     price=o_data["price"],
                        #     quantity=o_data["qty"],
                        #     timestamp=o_data.get("timestamp", 0),
                        # )
                        # # Add to book directly
                        # book.add_order(node)

                        # Restore original timestamp for FIFO priority
                        # add_order() creates a new timestamp (now). We overwrite it
                        # with the old one so the order keeps its place in line.
                        if "timestamp" in o_data and o_data["id"] in book._orders:
                            book._orders[o_data["id"]].timestamp = o_data["timestamp"]

                # Restore Bids and Asks
                restore_orders(market_data.get("bids", []), "buy")
                restore_orders(market_data.get("asks", []), "sell")

            except ValueError as e:
                print(f"[!] Error loading market {key_str}: {e}")
