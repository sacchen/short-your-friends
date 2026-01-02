from decimal import Decimal

from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    consumes,
    initialize,
    invariant,
    rule,
)

from orderbook.audit import SystemAuditor
from orderbook.economy import EconomyManager
from orderbook.engine import MatchingEngine

# Market ID helper: (target_user_id, threshold)
# We'll stick to one market for simplicity in fuzzing: ("alice", 10)
MARKET_ID_TUPLE = ("alice", 10)
MARKET_ID_STR = "alice,10"


class OrderBookFuzzer(RuleBasedStateMachine):
    """
    Acts as a 'Mock Server' to fuzz test the interaction between
    Economy (Money) and Engine (Order Book).
    """

    # Store Order IDs so we can cancel them later
    created_order_ids = Bundle("order_ids")

    @initialize()
    def setup_system(self) -> None:
        self.economy = EconomyManager()
        self.engine = MatchingEngine()

        # Initialize Auditor with BOTH components
        self.auditor = SystemAuditor(self.engine, self.economy)

        # 1. Setup Users & Funding
        # EconomyManager creates users implicitly when you deposit
        self.economy.deposit("alice", Decimal("10000.00"))
        self.economy.deposit("bob", Decimal("10000.00"))

        # 2. Setup Inventory (Shares)
        # Alice needs shares to sell. Bob needs shares to sell.
        # We manually inject shares into the portfolio for testing
        self.economy.get_account("alice").portfolio[MARKET_ID_STR] = 100
        self.economy.get_account("bob").portfolio[MARKET_ID_STR] = 100

        # 3. Create the Market in the Engine
        self.engine.create_market(MARKET_ID_TUPLE, "Alice > 10m")

        # Track internal order ID counter (Server usually does this)
        self.next_order_id = 1

    @rule(
        target=created_order_ids,
        side=st.sampled_from(["buy", "sell"]),
        price=st.integers(min_value=1, max_value=100),
        qty=st.integers(min_value=1, max_value=10),
        user=st.sampled_from(["alice", "bob"]),
    )
    def place_limit_order(self, side: str, price: int, qty: int, user: str) -> int:
        """
        Simulate Server Logic: Lock funds -> Place Order -> Settle Trades
        """
        order_id = self.next_order_id
        self.next_order_id += 1

        # Map string user to int user for the engine
        user_int = 1 if user == "alice" else 2

        # 1. LOCK FUNDS (Buyers only)
        if side == "buy":
            success = self.economy.attempt_order_lock(user_id=user, price=Decimal(price), quantity=qty)
            if not success:
                return order_id

        # 2. PLACE ORDER
        trades = self.engine.process_order(
            market_id=MARKET_ID_TUPLE,
            side=side,
            price=price,
            quantity=qty,
            order_id=order_id,
            user_id=user_int,
        )

        # 3. SETTLE TRADES
        for trade in trades:
            # FIX: Use correct field names from Trade class
            buyer_str = "alice" if trade.buy_user_id == 1 else "bob"
            seller_str = "alice" if trade.sell_user_id == 1 else "bob"

            self.economy.confirm_trade(
                buyer_id=buyer_str,
                seller_id=seller_str,
                market_id=MARKET_ID_STR,
                price=Decimal(trade.price),
                quantity=trade.quantity,
            )

        return order_id

    @rule(order_id=consumes(created_order_ids))
    def cancel_order(self, order_id: int) -> None:
        """
        Simulate Server Logic: Cancel Order -> Refund Locked Cash
        """
        # 1. Cancel in Engine
        metadata = self.engine.cancel_order(order_id)

        # 2. Refund (If it was a buy order)
        if metadata and metadata.side == "buy":
            self.economy.release_order_lock(
                user_id=str(metadata.user_id),
                price=Decimal(metadata.price),
                quantity=metadata.quantity,
            )

    @invariant()
    def verify_financial_integrity(self) -> None:
        """
        The Holy Grail:
        Total Cash in System must be conserved.
        Locked Cash in Economy == Value of Buy Orders in Engine.
        """
        self.auditor.run_full_audit()


TestOrderBookFuzzer = OrderBookFuzzer.TestCase
