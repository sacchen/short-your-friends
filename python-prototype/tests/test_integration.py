# Tests EconomyManager logic in server.py

# Usage:
# Start server: PYTHONPATH=src uv run server.py
# Start test:   uv run pytest tests/test_integration.py

import json
import socket


def send_request(sock, request_dict):
    """Helper to send JSON and get JSON response"""
    # 1. Convert Dict -> JSON String -> Bytes
    msg = json.dumps(request_dict).encode() + b"\n"
    sock.sendall(msg)

    # 2. Wait for response (read until newline)
    # Simple reader for testing
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Server closed connection")
        data += chunk

    return json.loads(data.decode().strip())


def test_integration():
    host = "127.0.0.1"
    port = 8888

    print(f"--- Connecting to {host}:{port} ---")

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        user = "test_user_1"

        # 1. Check Initial Balance (Should be 0)
        print("\n1. Checking Initial Balance...")
        resp = send_request(s, {"type": "balance", "user_id": user})
        print(f"Response: {resp}")
        assert resp["available"] == "0.00"

        # 2. Mint Money (Proof of Walk)
        print("\n2. Walking 10,000 steps...")
        # 10k steps * 0.01 = 100.00 credits
        resp = send_request(
            s, {"type": "proof_of_walk", "user_id": user, "steps": 10000}
        )
        print(f"Response: {resp}")
        assert resp["new_balance"] == "100.00"

        # 3. Place Buy Order (Lock Funds)
        print("\n3. Placing Buy Order (5 shares @ $10)...")
        # Cost = 50.00. Remaining should be 50.00
        req = {
            "type": "limit",
            "side": "buy",
            "price": 10,
            "qty": 5,
            "id": "order_1",
            "user_id": user,
            "market_id": {"target_user_id": "target_A", "threshold_minutes": 60},
        }
        resp = send_request(s, req)
        print(f"Response: {resp}")

        # 4. Check Balance (Should be 50 available, 50 locked)
        print("\n4. Verifying Locked Funds...")
        resp = send_request(s, {"type": "balance", "user_id": user})
        print(f"Response: {resp}")
        assert resp["available"] == "50.00"
        assert resp["locked"] == "50.00"

        # 5. Try to Overspend (Should Fail)
        print("\n5. Trying to overspend (Buy 60 worth)...")
        # We have 50 available. Trying to spend 60.
        req["id"] = "order_2"
        req["qty"] = 6  # 6 * 10 = 60
        resp = send_request(s, req)
        print(f"Response: {resp}")
        assert resp["status"] == "error"

        # 6. Cancel Order (Unlock Funds)
        print("\n6. Cancelling Order #1...")
        resp = send_request(s, {"type": "cancel", "id": "order_1"})
        print(f"Response: {resp}")

        # 7. Final Balance Check (Should be 100 available again)
        print("\n7. Final Balance Check...")
        resp = send_request(s, {"type": "balance", "user_id": user})
        print(f"Response: {resp}")
        assert resp["available"] == "100.00"
        assert resp["locked"] == "0.00"

        print("\n[+] TEST PASSED: Economy Integration works.")

    except Exception as e:
        print(f"\n[!] TEST FAILED: {e}")
    finally:
        s.close()


if __name__ == "__main__":
    test_integration()
