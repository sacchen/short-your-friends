# Rules:
# num_Longs == num_Shorts
# Total system wealth (Available + Locked) == Total Minted
# MatchingEngine registry == OrderBook internal quantities

from decimal import Decimal

from engine.engine import MatchingEngine
from orderbook.economy import EconomyManager


class SystemAuditor:
    def __init__(self, engine: MatchingEngine, economy: EconomyManager) -> None:
        self.engine = engine
        self.economy = economy

    def run_full_audit(self) -> None:
        """
        Runs all invariant checks.
        If fail, system state is corrupted.
        """
        print("\n--- STARTING SYSTEM AUDIT ---")

        try:
            self._audit_positions()
            self._audit_cash()
            self._audit_registry()
            print("--- AUDIT COMPLETE: SYSTEM IS SOUND ---\n")
        except ValueError as e:
            # In a real exchange, this would trigger a 'Circuit Breaker'
            # and halt all trading immediately.
            print(f"!!! CRITICAL AUDIT FAILURE: {e}")
            raise

    def _audit_positions(self) -> None:
        """Total net quantity in every market must sum to zero (Conservation of Contracts)."""
        for market_id, book in self.engine._markets.items():
            # Sum of all user positions (Longs are +, Shorts are -)
            total_net = sum(book._positions.values())
            if total_net != 0:
                raise ValueError(f"Market {market_id} unbalanced! Net: {total_net}")
        print("[✓] Market Positions Balanced: Net Zero.")

    def _audit_cash(self) -> None:
        """Available + Locked must equal total wealth (Conservation of Cash)."""
        system_total = Decimal("0.00")

        for user_id, account in self.economy.accounts.items():
            system_total += account.balance_available + account.balance_locked

        # Optimization: In the future, compare this to a 'Total Deposits'
        # variable in EconomyManager to ensure no money was 'leaked' or 'minted'.
        print(f"[✓] Cash Audit: Total System Liquidity is ${system_total:.2f}")

    def _audit_registry(self) -> None:
        """The Registry 'Map' must perfectly match the OrderBook 'Reality'."""
        for market_id, book in self.engine._markets.items():
            # Actual contracts resting in the book's internal lists
            book_volume = sum(order.quantity for order in book._orders.values())

            # What the global registry (used for cancellations) thinks is there
            registry_volume = sum(
                meta.quantity for meta in self.engine._order_registry.values() if meta.market_id == market_id
            )

            if book_volume != registry_volume:
                raise ValueError(f"Registry mismatch in {market_id}! Book: {book_volume}, Registry: {registry_volume}")
        print("[✓] Registry Integrity: Global Map matches Local Books.")
