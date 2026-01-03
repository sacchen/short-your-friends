"""
Test market ID persistence and duplicate prevention.

This test verifies the fix for duplicate market IDs where the same market
could appear twice in the client due to inconsistent username/ID conversion.
"""

from engine.engine import MatchingEngine
from orderbook.id_mapper import UserIdMapper


def test_market_id_no_duplicates_after_reload():
    """Verify markets don't appear twice after save/load cycle."""
    engine = MatchingEngine()
    mapper = UserIdMapper()

    # Create market for alice (internal ID will be assigned by mapper)
    alice_id = mapper.to_internal("alice")
    market_id = (alice_id, 480)
    engine.create_market(market_id, "Alice Sleep 8:00")

    # Place some orders to have realistic state
    engine.process_order(
        market_id=market_id, side="buy", price=40, quantity=5, order_id=1, user_id=alice_id
    )
    engine.process_order(
        market_id=market_id, side="sell", price=60, quantity=10, order_id=2, user_id=alice_id
    )

    # Save state
    saved_state = engine.dump_state()

    # Verify saved state has string keys, not tuples
    assert isinstance(list(saved_state["markets"].keys())[0], str)
    market_key = list(saved_state["markets"].keys())[0]
    assert "," in market_key  # Should be format "1,480"

    # Load into fresh engine
    engine2 = MatchingEngine()
    engine2.load_state(saved_state)

    # Get all markets
    markets = engine2.get_active_markets()

    # CRITICAL: Should be exactly 1 market, not duplicated
    assert len(markets) == 1
    assert markets[0]["id"] == f"{alice_id}_{480}"


def test_string_username_in_saved_state_is_skipped():
    """
    Verify that if saved state contains string usernames (legacy format),
    they are logged and skipped rather than creating duplicate markets.
    """
    engine = MatchingEngine()

    # Create malformed state with string username
    bad_state = {
        "markets": {
            "alice,480": {  # BAD: String username instead of internal ID
                "name": "Alice Sleep 8:00",
                "bids": [],
                "asks": [],
            }
        }
    }

    # Load should skip invalid market and log warning
    engine.load_state(bad_state)

    # Verify market was NOT created
    assert len(engine._markets) == 0
    markets = engine.get_active_markets()
    assert len(markets) == 0


def test_numeric_id_in_saved_state_loads_correctly():
    """Verify numeric IDs in saved state load correctly."""
    engine = MatchingEngine()

    # Create valid state with numeric ID
    good_state = {
        "markets": {
            "1,480": {  # GOOD: Numeric internal ID
                "name": "Test Market",
                "bids": [],
                "asks": [],
            }
        }
    }

    # Load should work
    engine.load_state(good_state)

    # Verify market was created with tuple (1, 480)
    assert len(engine._markets) == 1
    assert (1, 480) in engine._markets

    markets = engine.get_active_markets()
    assert len(markets) == 1
    assert markets[0]["id"] == "1_480"


def test_save_format_uses_numeric_ids():
    """Verify engine.dump_state() always uses numeric internal IDs."""
    engine = MatchingEngine()
    mapper = UserIdMapper()

    # Create markets for multiple users
    alice_id = mapper.to_internal("alice")
    bob_id = mapper.to_internal("bob")

    engine.create_market((alice_id, 480), "Alice 8:00")
    engine.create_market((bob_id, 360), "Bob 6:00")

    # Dump state
    state = engine.dump_state()

    # Verify all keys are numeric format
    for key in state["markets"].keys():
        parts = key.split(",")
        assert len(parts) == 2
        # First part should be parseable as int
        assert parts[0].isdigit(), f"Key {key} has non-numeric user ID"
        assert parts[1].isdigit(), f"Key {key} has non-numeric threshold"


def test_load_and_save_cycle_preserves_format():
    """Verify save → load → save produces consistent format."""
    engine1 = MatchingEngine()
    mapper = UserIdMapper()

    # Create original market
    alice_id = mapper.to_internal("alice")
    market_id = (alice_id, 480)
    engine1.create_market(market_id, "Alice 8:00")

    # First save
    state1 = engine1.dump_state()

    # Load into new engine
    engine2 = MatchingEngine()
    engine2.load_state(state1)

    # Second save
    state2 = engine2.dump_state()

    # Compare states - should be identical
    assert state1 == state2
    assert list(state1["markets"].keys()) == list(state2["markets"].keys())
