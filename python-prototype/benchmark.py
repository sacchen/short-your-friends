"""
Usage: uv run python benchmark.py
at short-your-friends/python-prototype
"""

import sys
from pathlib import Path

# Add src to Python path so we can import orderbook
sys.path.insert(0, str(Path(__file__).parent / "src"))

import random
import time

from orderbook.book import OrderBook


def run_benchmark(n_orders: int = 100_000) -> None:
    book = OrderBook()

    # Two users trade
    book.process_order("buy", price=100, quantity=10, order_id=1, user_id=100)
    book.process_order("sell", price=100, quantity=10, order_id=2, user_id=200)

    print(book._positions)  # Should show {100: 10, 200: -10}

    # Pre-generate data so we measure the ENGINE, not the random number generator
    print(f"Generating {n_orders} random orders...")
    orders: list[tuple[str, int, int, int]] = []
    for i in range(n_orders):
        side = "buy" if random.random() < 0.5 else "sell"
        price = random.randint(90, 110)  # Tight spread to force matches
        qty = random.randint(1, 10)
        orders.append((side, price, qty, i))

    print("Starting benchmark...")
    start_time = time.time()

    matches = 0
    for i, (side, price, qty, oid) in enumerate(orders):
        user_id = i  # stand-in user_id
        trades = book.process_order(side, price, qty, oid, user_id)
        matches += len(trades)

    end_time = time.time()
    duration = end_time - start_time
    ops = n_orders / duration

    print("\n--- Results ---")
    print(f"Processed {n_orders:,} orders in {duration:.4f} seconds")
    print(f"Throughput: {ops:,.0f} orders/second")
    print(f"Total Trades Executed: {matches:,}")

    # Validation check (book shouldn't be empty, but shouldn't have 100k orders)
    print(f"Remaining Bids in Heap: {len(book._bids_heap)}")
    print(f"Remaining Asks in Heap: {len(book._asks_heap)}")


if __name__ == "__main__":
    run_benchmark()
