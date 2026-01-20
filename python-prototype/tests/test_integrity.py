# tests audit.py

import random
from decimal import Decimal

from engine.engine import MatchingEngine
from orderbook.audit import SystemAuditor
from orderbook.economy import EconomyManager


def test_system_stress() -> None:
    engine = MatchingEngine()
    economy = EconomyManager()
    auditor = SystemAuditor(engine, economy)

    # Setup: Create a few users with money
    users = ["user_1", "user_2", "user_3"]
    for u in users:
        account = economy.get_account(u)
        account.balance_available = Decimal("1000.00")
        # economy.deposit(
        #     u, Decimal("1000.00")
        # )

    market_id = ("alice", 480)

    print("Running 100 random operations...")
    for i in range(100):
        user = random.choice(users)
        side = random.choice(["buy", "sell"])
        price = random.randint(90, 110)  # Price in cents
        qty = random.randint(1, 10)

        # 1. Place Order
        try:
            # Note: You'd call your server-level logic here to handle the
            # Economy locks and Engine processing together.
            engine.process_order(market_id, side, price, qty, i, user)
        except Exception:
            pass  # Handle expected engine rejections

        # 2. MOMENT OF TRUTH
        auditor.run_full_audit()


if __name__ == "__main__":
    test_system_stress()

# Failure Type and What it means
# Market unbalanced: book.process_order logic is failing to update the buyer's and seller's positions equally. One side is ""leaking"" contracts.
# Cash Audit Failure: likely have a bug in release_order_lock. either
# double-refunding or failing to unlock money when an order is cancelled or filled.
# Registry Mismatch: This confirms the ""Partial Fill"" logic. If fail, the registry (the global map) is out of sync with the actual orders resting on the book.
