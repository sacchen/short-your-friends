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

    def get_or_create_market(self, market_id: MarketId) -> OrderBook:
        if market_id not in self._markets:
            self._markets[market_id] = OrderBook()
        return self._markets[market_id]

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
        results = []
        for market_id, book in self._markets.items():
            target_user, minutes = market_id

            # Get best prices for the "ticker"
            best_bid = book.bids[0].price if book.bids else None
            best_ask = book.asks[0].price if book.asks else None

            results.append(
                {
                    "target_user": target_user,
                    "threshold_minutes": minutes,
                    "best_bid": str(best_bid) if best_bid else None,
                    "best_ask": str(best_ask) if best_ask else None,
                    "volume": 0,  # TODO: track volume
                }
            )
        return results

    # TODO: add get_market_details() that returns graph data/history
