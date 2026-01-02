import json
import os
import socket
import uuid
from typing import Any

# Configuration via environment variables
HOST = os.getenv("TEST_SERVER_HOST", "127.0.0.1")
PORT = int(os.getenv("TEST_SERVER_PORT", "8888"))


def send_request(sock: socket.socket, request_dict: dict[str, Any]) -> dict[str, Any]:
    """Helper to send JSON and get JSON response"""
    msg = json.dumps(request_dict).encode() + b"\n"
    sock.sendall(msg)

    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Server closed connection")
        data += chunk
    result: dict[str, Any] = json.loads(data.decode().strip())
    return result


def test_integration() -> None:
    # Use a unique test user for THIS specific test run
    user = f"test_user_{uuid.uuid4().hex[:8]}"

    print(f"--- Connecting to {HOST}:{PORT} as {user} ---")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((HOST, PORT))

        # 1. Check Initial Balance (Should be 0.00)
        resp = send_request(s, {"type": "balance", "user_id": user})
        assert resp["available"] == "0.00"

        # 2. Mint Money (Proof of Walk)
        resp = send_request(s, {"type": "proof_of_walk", "user_id": user, "steps": 10000})
        assert resp["new_balance"] == "100.00"

        # 3. Place Buy Order (Lock Funds)
        req = {
            "type": "place_order",
            "side": "buy",
            "price": 1000,  # cents
            "qty": 5,
            "id": f"order_{uuid.uuid4().hex[:4]}",
            "user_id": user,
            "market_id": {"target_user_id": "target_A", "threshold_minutes": 60},
        }
        resp = send_request(s, req)

        # DEBUG
        print(f"Order response: {resp}")  # Add this to see the error
        assert resp["status"] == "ok", f"Expected 'ok', got {resp}"

        if resp.get("status") != "ok":
            print(f"ERROR: {resp.get('message', 'Unknown error')}")
            print(f"Full response: {resp}")
        assert resp["status"] == "ok", f"Order failed: {resp.get('message', 'Unknown error')}"

        # 4. Check Balance (Should be 50 available, 50 locked)
        resp = send_request(s, {"type": "balance", "user_id": user})
        assert resp["available"] == "50.00"
        assert resp["locked"] == "50.00"

        print(f"[+] SUCCESS: Integration flow passed for {user}")

    finally:
        s.close()


if __name__ == "__main__":
    test_integration()
