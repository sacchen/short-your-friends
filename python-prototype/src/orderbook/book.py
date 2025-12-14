import heapq
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .linked_list import OrderList
from .node import OrderNode
from .trade import Trade


@dataclass
class OrderBook:
    # Order ID -> OrderNode
    _orders: Dict[int, OrderNode] = field(default_factory=dict)

    # Price -> OrderList
    _bids: Dict[int, OrderList] = field(default_factory=dict)
    _asks: Dict[int, OrderList] = field(default_factory=dict)

    # Heaps with lazy deletion
    # _bids_heap stores -price since heapq is a Min-Heap
    _bids_heap: List[int] = field(default_factory=list)
    _asks_heap: List[int] = field(default_factory=list)

    def process_order(
        self, side: str, price: int, quantity: int, order_id: int
    ) -> List[Trade]:
        """
        Matches the order against the book.
        Remainder of partial matches is added to the book.
        """
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
                        )
                    )

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
                            buy_order_id=maker_order.order_id,  # Maker is the Buyer here
                            sell_order_id=order_id,  # We (Taker) are the Seller
                            price=best_bid_price,  # Trade at Maker's price
                            quantity=trade_qty,
                            maker_order_id=maker_order.order_id,
                            taker_order_id=order_id,
                        )
                    )

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
            self._add_to_book(side, price, remaining_qty, order_id)

        return trades

    def _add_to_book(self, side: str, price: int, quantity: int, order_id: int) -> None:
        """
        Places a resting order in the book
        Doesn't match orders
        """
        # Create order node
        order = OrderNode(
            order_id=order_id, price=price, quantity=quantity, timestamp=time.time()
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

    def get_best_bid(self) -> Optional[int]:
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

    def get_best_ask(self) -> Optional[int]:
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
