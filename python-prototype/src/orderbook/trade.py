from dataclasses import dataclass


@dataclass(slots=True)
class Trade:
    buy_order_id: int
    sell_order_id: int
    price: int
    quantity: int
    maker_order_id: int  # Existing order
    taker_order_id: int  # New order that triggers trade
