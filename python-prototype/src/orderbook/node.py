from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class OrderNode:
    # Data
    order_id: int
    user_id: int
    price: int
    quantity: int
    timestamp: float

    # Pointers
    next_node: Optional["OrderNode"] = None
    prev_node: Optional["OrderNode"] = None

    def __repr__(self) -> str:
        return f"Order(id={self.order_id}, price={self.price}, qty={self.quantity})"
