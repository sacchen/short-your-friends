import heapq
import time
from dataclasses import dataclass, field
from typing import Dict, List

from .linked_list import OrderList
from .node import OrderNode


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

    def add_order(self, side: str, price: int, quantity: int, order_id: int) -> None:
        """
        Places a resting order in the book
        Doesn't match orders
        """
        # Create order node
        order = OrderNode(
            order_id=order_id, price=price, quantity=quantity, timestamp=time.time()
        )

        # Store in global map
        self._orders[order_id] = order

        # Add to buy or sell side
        if side == "buy":
            if price not in self._bids:
                self._price[price] = OrderList()
                heapq.heappush(self._bids_heap, -price)  # Max-Heap
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
