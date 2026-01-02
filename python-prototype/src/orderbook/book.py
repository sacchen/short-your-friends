import heapq
import time
from dataclasses import dataclass, field

from .linked_list import OrderList
from .node import OrderNode
from .trade import Trade
from .types import PriceLevel


@dataclass
class OrderBook:
    # Find order
    # Order ID -> OrderNode
    _orders: dict[int, OrderNode] = field(default_factory=dict)

    # Price Levels
    # Price -> OrderList
    # Key=Price, Value=Linked List of orders at that price
    _bids: dict[int, OrderList] = field(default_factory=dict)
    _asks: dict[int, OrderList] = field(default_factory=dict)

    # Sorted prices
    # Heaps with lazy deletion
    # _bids_heap stores -price since heapq is a Min-Heap
    _bids_heap: list[int] = field(default_factory=list)
    _asks_heap: list[int] = field(default_factory=list)

    # Track net positions per user
    _positions: dict[int, int] = field(default_factory=dict)  # user_id -> net_qty

    # Track if market is open
    active: bool = True

    def process_order(
        self,
        side: str,
        price: int,
        quantity: int,
        order_id: int,
        user_id: int,
    ) -> list[Trade]:
        """
        Matches the order against the book.
        Remainder of partial matches is added to the book.
        """
        # Gatekeeper
        if not self.active:
            print("DEBUG: Order rejected because market is CLOSED")
            # raise exception or return error
            raise ValueError("Market is closed.")

        trades = []
        remaining_qty = quantity

        if side == "buy":
            # While there is qty to buy and there are sellers
            while remaining_qty > 0 and self._asks_heap:
                best_ask_price = self._asks_heap[0]

                # Does Buy Price >= Best Sell Price?
                if price < best_ask_price:
                    break

                # Get the queue of order at this best price
                # lazy deletion here?
                if best_ask_price not in self._asks:
                    heapq.heappop(self._asks_heap)
                    continue

                best_ask_queue = self._asks[best_ask_price]

                # Go thru queue (Time Priority)
                # Head is oldest order
                while remaining_qty > 0 and best_ask_queue.head:
                    maker_order = best_ask_queue.head

                    # Calculate trade size
                    trade_qty = min(remaining_qty, maker_order.quantity)

                    # Execute Trade
                    trades.append(
                        Trade(
                            buy_order_id=order_id,
                            sell_order_id=maker_order.order_id,
                            price=best_ask_price,  # Trade at Maker's price
                            quantity=trade_qty,
                            maker_order_id=maker_order.order_id,
                            taker_order_id=order_id,
                            buy_user_id=user_id,  # taker is buyer
                            sell_user_id=maker_order.user_id,  # maker is seller
                        )
                    )

                    # Update positions
                    self._positions[user_id] = self._positions.get(user_id, 0) + trade_qty
                    self._positions[maker_order.user_id] = self._positions.get(maker_order.user_id, 0) - trade_qty

                    # Update quantities
                    remaining_qty -= trade_qty
                    maker_order.quantity -= trade_qty
                    best_ask_queue.total_volume -= trade_qty

                    # If maker order is filled, remove it
                    if maker_order.quantity == 0:
                        best_ask_queue.remove(maker_order)
                        del self._orders[maker_order.order_id]

                # If the queue is empty, remove it
                if best_ask_queue.count == 0:
                    del self._asks[best_ask_price]
                    heapq.heappop(self._asks_heap)

        elif side == "sell":
            # Sell logic checks Bids

            # Check against Bids
            while remaining_qty > 0 and self._bids_heap:
                # Bids are stored as negative numbers
                # Flip it back
                best_bid_price = -self._bids_heap[0]

                # Check Spread
                # No deal if Sell Price > Best Bid
                if price > best_bid_price:
                    break

                # Lazy deletion check
                # Earlier we marked the node for deletion and now we're doing it.
                if best_bid_price not in self._bids:
                    heapq.heappop(self._bids_heap)
                    continue

                best_bid_queue = self._bids[best_bid_price]

                # Go thru Queue (Time Priority)
                while remaining_qty > 0 and best_bid_queue.head:
                    maker_order = best_bid_queue.head  # This is "buy" order

                    trade_qty = min(remaining_qty, maker_order.quantity)

                    # Trade Receipt
                    # Arguments are flipped
                    trades.append(
                        Trade(
                            buy_order_id=maker_order.order_id,  # Maker is the Buyer
                            sell_order_id=order_id,  # We (Taker) are the Seller
                            price=best_bid_price,  # Trade at Maker's price
                            quantity=trade_qty,
                            maker_order_id=maker_order.order_id,
                            taker_order_id=order_id,
                            buy_user_id=maker_order.user_id,  # maker is buyer
                            sell_user_id=user_id,  # taker is seller
                        )
                    )

                    # Update positions
                    self._positions[maker_order.user_id] = self._positions.get(maker_order.user_id, 0) + trade_qty
                    self._positions[user_id] = self._positions.get(user_id, 0) - trade_qty

                    remaining_qty -= trade_qty
                    maker_order.quantity -= trade_qty
                    best_bid_queue.total_volume -= trade_qty

                    if maker_order.quantity == 0:
                        best_bid_queue.remove(maker_order)
                        del self._orders[maker_order.order_id]

                if best_bid_queue.count == 0:
                    del self._bids[best_bid_price]
                    heapq.heappop(self._bids_heap)

        # If there is anything left, put it on the book
        if remaining_qty > 0:
            self._add_to_book(side, price, remaining_qty, order_id, user_id)

        return trades

    def _add_to_book(self, side: str, price: int, quantity: int, order_id: int, user_id: int) -> None:
        """
        Places a resting order in the book
        Doesn't match orders
        """
        # Gatekeeper
        if not self.active:
            raise ValueError("Market is closed.")

        # Create order node
        order = OrderNode(
            order_id=order_id,
            user_id=user_id,
            price=price,
            quantity=quantity,
            timestamp=time.time(),
        )

        # Store in global map
        # Find the slot called "order_id" in _orders dictionary and put "order" there.
        self._orders[order_id] = order

        # Add to buy or sell side
        if side == "buy":
            # Do we already have a queue for this price?
            if price not in self._bids:
                # If no, create a new empty queue
                self._bids[price] = OrderList()
                # Tell Heap about this new price level
                # Heap: Price priority
                heapq.heappush(self._bids_heap, -price)  # Max-Heap
            # Place order at the end of queue
            # Queue: Time priority
            self._bids[price].append(order)

        elif side == "sell":
            if price not in self._asks:
                self._asks[price] = OrderList()
                heapq.heappush(self._asks_heap, price)
            self._asks[price].append(order)

    def add_order(self, side: str, price: int, quantity: int, order_id: int, user_id: int) -> None:
        """
        Public method to add a resting order to the book without matching.
        For matching orders, use process_order() instead.
        """
        self._add_to_book(side, price, quantity, order_id, user_id)

    def cancel_order(self, order_id: int) -> None:
        """
        Cancels an order
        Uses hash map and doubly linked list
        O(1)
        """
        if order_id not in self._orders:
            return

        order = self._orders[order_id]
        price = order.price

        # Remove from the Linked List
        if price in self._bids:
            self._bids[price].remove(order)
            # If level is empty, delete the list from the dict
            # Leave the price in the heap for lazy deletion
            if self._bids[price].count == 0:
                del self._bids[price]

        elif price in self._asks:
            self._asks[price].remove(order)
            if self._asks[price].count == 0:
                del self._asks[price]

        # Remove from global map
        del self._orders[order_id]

    def get_best_bid(self) -> int | None:
        """
        Returns the highest buy price.
        Lazy clean up ghost prices from the heap.
        """
        while self._bids_heap:
            # Bids were stored as negatives, so flipping it back
            best_price_neg = self._bids_heap[0]
            best_price = -best_price_neg

            if best_price in self._bids:
                return best_price
            else:
                # This price level is now empty, so pop and retry
                heapq.heappop(self._bids_heap)
        return None

    def get_best_ask(self) -> int | None:
        """
        Returns the lowest sell price.
        """
        while self._asks_heap:
            best_price = self._asks_heap[0]

            if best_price in self._asks:
                return best_price
            else:
                heapq.heappop(self._asks_heap)
        return None

    def snapshot(self) -> dict[str, list[PriceLevel]]:
        """
        Returns a snapshot of the current order book as lists of price levels.
        Bids are sorted descending by price, asks ascending.
        """
        bids: list[PriceLevel] = []
        for price, order_list in sorted(self._bids.items(), reverse=True):
            bids.append(
                {
                    "price": price,
                    "volume": order_list.total_volume,
                    "count": order_list.count,
                }
            )

        asks: list[PriceLevel] = []
        for price, order_list in sorted(self._asks.items()):
            asks.append(
                {
                    "price": price,
                    "volume": order_list.total_volume,
                    "count": order_list.count,
                }
            )

        return {"bids": bids, "asks": asks}

    SYSTEM_USER_ID = 0  # Reserved system account

    def settle_market(self, terminal_price: int) -> list[Trade]:
        """
        Settle entire market at terminal_price (0 or 1).
        Cancels all orders and settles all positions.
        """
        self.active = False
        print(f"DEBUG: Market is now CLOSED (Active={self.active})")

        trades: list[Trade] = []

        # Cancel all resting orders
        orders_to_cancel = list(self._orders.keys())
        for old in orders_to_cancel:
            self.cancel_order(old)

        # Settle positions
        for user_id, net_qty in self._positions.items():
            if net_qty == 0:
                continue

            # Create synthetic trade
            if net_qty > 0:  # Long position
                qty = net_qty
                if terminal_price == 1:
                    buy_user, sell_user = user_id, self.SYSTEM_USER_ID
                else:
                    buy_user, sell_user = self.SYSTEM_USER_ID, user_id
            else:  # Short position
                qty = -net_qty
                if terminal_price == 1:
                    buy_user, sell_user = self.SYSTEM_USER_ID, user_id
                else:
                    buy_user, sell_user = user_id, self.SYSTEM_USER_ID

            trades.append(
                Trade(
                    buy_order_id=-1,
                    sell_order_id=-1,
                    price=terminal_price,
                    quantity=qty,
                    maker_order_id=-1,
                    taker_order_id=-1,
                    buy_user_id=buy_user,
                    sell_user_id=sell_user,
                )
            )

            self._positions[user_id] = 0

        return trades
