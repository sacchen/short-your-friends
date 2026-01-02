import uuid
from typing import Any

import pytest

from server import OrderBookServer


@pytest.mark.asyncio
async def test_full_user_flow() -> None:
    # 1. Setup: Instantiate server directly (No TCP socket needed)
    server = OrderBookServer()
    # Load/seed data if we want "market_maker" to exist
    server.seed_dev_data()

    # 2. Define our user and dummy address
    user = f"test_user_{uuid.uuid4().hex[:8]}"
    addr = "internal_test"

    # --- Step A: Check Initial Balance ---
    # Call process_request directly. It expects a Dict, returns a Dict.
    req_balance = {"type": "balance", "user_id": user}
    resp_balance: dict[str, Any] = await server.process_request(req_balance, addr)  # type: ignore[assignment]

    # BLANK: What should the available balance be?
    assert resp_balance["available"] == "0.00"

    # --- Step B: Proof of Walk (Mint Money) ---
    req_walk = {"type": "proof_of_walk", "user_id": user, "steps": 10000}
    resp_walk: dict[str, Any] = await server.process_request(req_walk, addr)  # type: ignore[assignment]

    assert resp_walk["status"] == "ok"
    assert resp_walk["new_balance"] == "100.00"

    # --- Step C: Place Buy Order ---
    req_order = {
        "type": "place_order",
        "side": "buy",
        "price": 1000,  # 1000 cents = $10.00
        "qty": 5,
        "id": "order_1",
        "user_id": user,
        # BLANK: The new Interface handles this dict format.
        # Does the Interface expect "target_user_id" or just "market_id"?
        # Request key is "market_id"
        # You can pass a dict (inc. target_user_id) or string
        # since translate_client_message in Interface handles both.
        "market_id": {"target_user_id": "target_A", "threshold_minutes": 60},
    }

    resp_order = await server.process_request(req_order, addr)

    # Assert success
    assert resp_order["status"] == "ok"

    # --- Step D: Verify Locking ---
    # Check balance again to ensure funds are locked
    resp_final: dict[str, Any] = await server.process_request(req_balance, addr)  # type: ignore[assignment]

    # $10.00 * 5 = $50.00 locked
    assert resp_final["available"] == "50.00"
    assert resp_final["locked"] == "50.00"
