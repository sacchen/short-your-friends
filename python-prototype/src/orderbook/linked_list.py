from collections.abc import Iterator
from dataclasses import dataclass

from .node import OrderNode


@dataclass(slots=True)
class OrderList:
    head: OrderNode | None = None  # just one OrderNode, or None
    tail: OrderNode | None = None
    count: int = 0
    total_volume: int = 0

    def append(self, order: OrderNode) -> None:
        """
        Adds an order to the end of the queue (time priority)
        O(1)
        """
        self.count += 1
        self.total_volume += order.quantity

        if self.tail is None:
            # List is empty
            self.head = order
            self.tail = order
            order.prev_node = None
            order.next_node = None
        else:
            # Append to end
            self.tail.next_node = order
            order.prev_node = self.tail
            order.next_node = None
            self.tail = order

    def remove(self, order: OrderNode) -> None:
        """
        Removes the given order from the list
        O(1)
        """
        self.total_volume -= order.quantity
        self.count -= 1

        # Update head if needed
        if order.prev_node is None:
            self.head = order.next_node
        else:
            # Update previous node
            order.prev_node.next_node = order.next_node

        # Update tail or connect next node
        if order.next_node is None:
            self.tail = order.prev_node  # If no next_node, remove the tail
        else:
            # Update next node
            order.next_node.prev_node = order.prev_node

        # Remove pointers of removed node
        order.next_node = None
        order.prev_node = None

    def __iter__(self) -> Iterator[OrderNode]:
        current = self.head
        while current:
            yield current  # Returns first item and waits to give next item
            current = current.next_node
