"""
Usage: uv run python benchmark.py
at short-your-friends/python-prototype
"""

import sys
from pathlib import Path

# Add src to Python path so we can import orderbook
sys.path.insert(0, str(Path(__file__).parent / "src"))

import random
import statistics
import time

from orderbook.book import OrderBook


def run_benchmark(n_orders: int = 100_000, n_iterations: int = 10) -> None:
    """
    Run multiple benchmark iterations and report average throughput.
    """
    print(f"Running {n_iterations} iterations of {n_orders:,} orders each...")
    print("=" * 60)

    throughputs = []

    for iteration in range(n_iterations):
        book = OrderBook()

        # Pre-generate data so we measure the ENGINE, not the random number generator
        orders: list[tuple[str, int, int, int]] = []
        for i in range(n_orders):
            side = "buy" if random.random() < 0.5 else "sell"
            price = random.randint(90, 110)  # Tight spread to force matches
            qty = random.randint(1, 10)
            orders.append((side, price, qty, i))

        start_time = time.perf_counter()

        matches = 0
        for i, (side, price, qty, oid) in enumerate(orders):
            user_id = i
            trades = book.process_order(side, price, qty, oid, user_id)
            matches += len(trades)

        end_time = time.perf_counter()
        duration = end_time - start_time
        ops = n_orders / duration
        throughputs.append(ops)

        print(
            f"Iteration {iteration + 1:2d}: {ops:,.0f} orders/sec ({duration:.4f}s, {matches:,} trades)"
        )

    # Calculate average
    avg_throughput = statistics.mean(throughputs)

    print("\n" + "=" * 60)
    print("--- Results ---")
    print(f"Average Throughput: {avg_throughput:,.0f} orders/second")
    print(f"Min: {min(throughputs):,.0f} orders/second")
    print(f"Max: {max(throughputs):,.0f} orders/second")


if __name__ == "__main__":
    run_benchmark()
