from dataclasses import dataclass, field
from decimal import Decimal
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
        Serializes the exchange state to JSON.
        Structure:
        {
            "market_key_str": {
                "bids": [ {order_dict}, ... ],
                "asks": [ {order_dict}, ... ]
            }
        }
        """
        state = {}
        for market_id, book in self._markets.items():
            # Composite key needs to be a string for JSON
            # key is tuple before converting to string
            # key format: "user_id:minutes"
            key = f"{market_id[0]}:{market_id[1]}"

            # Helper to convert a list of Orders to dicts
            def serialize_orders(orders):
                return [
                    {
                        "id": o.order_id,
                        "user_id": o.user_id,
                        "price": str(o.price),
                        "qty": o.quantity,
                        "side": o.side,  # "buy" or "sell"
                    }
                    for o in orders
                ]

            state[key] = {
                "bids": serialize_orders(book._bids),
                "asks": serialize_orders(book._asks),
            }
        return state

    def load_state(self, data: dict) -> None:
        """Restores exchange state."""
        self._markets.clear()

        for key, book_data in data.items():
            # Parse key "user_id:minutes" back to tuple
            target_user, minutes_str = key.split(":")
            market_id = (target_user, int(minutes_str))

            # Recreate orders
            for side in ["bids", "asks"]:
                for o_data in book_data.get(side, []):
                    # Process as new orders to rebuild the book structures
                    # (safer than inserting into lists)
                    self.process_order(
                        market_id=market_id,
                        side=o_data["side"],
                        price=Decimal(o_data["price"]),
                        quantity=int(o_data["qty"]),
                        order_id=o_data["id"],
                        user_id=o_data["user_id"],
                    )
