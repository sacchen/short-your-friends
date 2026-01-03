"""
Test registry sync for partial fills.

This test verifies the fix for the registry mismatch bug where partial fills
don't update the registry when the maker order wasn't previously registered.
"""

from decimal import Decimal

from engine.engine import MatchingEngine
from orderbook.economy import EconomyManager


def test_partial_fill_updates_registry():
    """Verify registry is updated when maker order is partially filled."""
    engine = MatchingEngine()
    economy = EconomyManager()

    # Setup: Create market
    market_id = (1, 480)  # (user_id=1, threshold=480 minutes)
    engine.create_market(market_id, "Test Market")

    # Fund both users
    economy.get_account("user_1").balance_available = Decimal("100.00")
    economy.get_account("user_2").balance_available = Decimal("100.00")

    # Scenario: Maker places sell order (10 contracts at $0.60)
    # Taker partially fills it (buys only 3 contracts)

    # Step 1: Maker places sell order
    trades1 = engine.process_order(
        market_id=market_id, side="sell", price=60, quantity=10, order_id=1, user_id=1
    )
    assert len(trades1) == 0  # No match, order rests on book
    assert 1 in engine._order_registry  # Should be registered
    assert engine._order_registry[1].quantity == 10

    # Step 2: Taker partially fills (buy 3 out of 10)
    trades2 = engine.process_order(
        market_id=market_id, side="buy", price=60, quantity=3, order_id=2, user_id=2
    )

    # Verify trade occurred
    assert len(trades2) == 1
    assert trades2[0].quantity == 3
    assert trades2[0].maker_order_id == 1

    # CRITICAL: Registry must reflect remaining 7 contracts
    assert 1 in engine._order_registry
    assert engine._order_registry[1].quantity == 7

    # Verify book also has 7 remaining
    assert 1 in engine._markets[market_id]._orders
    assert engine._markets[market_id]._orders[1].quantity == 7


def test_partial_fill_missing_registry_entry():
    """
    Test the bug fix: maker order exists in book but NOT in registry.

    This can happen when:
    - Order was placed before registry tracking existed
    - Order was loaded from state without rebuilding registry
    - Registry was cleared but book wasn't

    The fix reconstructs the registry entry from book state.
    """
    engine = MatchingEngine()
    economy = EconomyManager()

    # Setup
    market_id = (1, 480)
    engine.create_market(market_id, "Test Market")
    economy.get_account("user_1").balance_available = Decimal("100.00")
    economy.get_account("user_2").balance_available = Decimal("100.00")

    # Step 1: Maker places sell order
    trades1 = engine.process_order(
        market_id=market_id, side="sell", price=60, quantity=10, order_id=1, user_id=1
    )
    assert len(trades1) == 0
    assert 1 in engine._order_registry

    # Step 2: SIMULATE BUG - Remove from registry but keep in book
    # (This simulates the missing registry entry scenario)
    del engine._order_registry[1]
    assert 1 not in engine._order_registry
    assert 1 in engine._markets[market_id]._orders  # Still in book

    # Step 3: Taker partially fills
    # OLD BUG: Registry not updated because order_id not in registry
    # NEW FIX: Reconstructs registry entry in the else clause
    trades2 = engine.process_order(
        market_id=market_id, side="buy", price=60, quantity=3, order_id=2, user_id=2
    )

    # Verify trade occurred
    assert len(trades2) == 1
    assert trades2[0].quantity == 3

    # CRITICAL: Registry should now exist with remaining quantity
    assert 1 in engine._order_registry
    assert engine._order_registry[1].quantity == 7
    assert engine._order_registry[1].side == "sell"
    assert engine._order_registry[1].price == 60


def test_registry_rebuild_after_load_state():
    """Verify _rebuild_registry() reconstructs registry from book state."""
    engine = MatchingEngine()
    market_id = (1, 480)

    # Step 1: Create market and place orders
    engine.create_market(market_id, "Test Market")
    engine.process_order(
        market_id=market_id, side="buy", price=40, quantity=5, order_id=1, user_id=1
    )
    engine.process_order(
        market_id=market_id, side="sell", price=60, quantity=10, order_id=2, user_id=2
    )

    # Verify registry populated
    assert len(engine._order_registry) == 2
    assert engine._order_registry[1].quantity == 5
    assert engine._order_registry[2].quantity == 10

    # Step 2: Save state
    saved_state = engine.dump_state()

    # Step 3: Load into fresh engine
    engine2 = MatchingEngine()
    engine2.load_state(saved_state)

    # CRITICAL: Registry should be rebuilt from book state
    assert len(engine2._order_registry) == 2
    assert 1 in engine2._order_registry
    assert 2 in engine2._order_registry
    assert engine2._order_registry[1].quantity == 5
    assert engine2._order_registry[1].side == "buy"
    assert engine2._order_registry[2].quantity == 10
    assert engine2._order_registry[2].side == "sell"


def test_full_fill_removes_from_registry():
    """Verify fully filled orders are removed from registry."""
    engine = MatchingEngine()
    market_id = (1, 480)
    engine.create_market(market_id, "Test Market")

    # Maker places sell order
    engine.process_order(
        market_id=market_id, side="sell", price=60, quantity=5, order_id=1, user_id=1
    )
    assert 1 in engine._order_registry

    # Taker fully fills it
    trades = engine.process_order(
        market_id=market_id, side="buy", price=60, quantity=5, order_id=2, user_id=2
    )

    assert len(trades) == 1
    assert trades[0].quantity == 5

    # CRITICAL: Fully filled order should be removed from registry
    assert 1 not in engine._order_registry
    assert 1 not in engine._markets[market_id]._orders
