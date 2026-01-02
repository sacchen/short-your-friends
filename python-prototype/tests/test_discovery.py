# tests/test_discovery.py
# Usage: uv run pytest tests/test_discovery.py

# We'll have to use Apple's Network.framework (NWConnection)
# to send raw strings ending in `\n`
import json
import socket
from typing import Any


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


def test_market_discovery() -> None:
    """Test that markets can be created and discovered"""
    import os

    host = os.getenv("EXCHANGE_IP", "127.0.0.1")
    port = 8888

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))

        # 1. Create a market implicitly by placing an order
        print("Creating market via order...")
        req = {
            "type": "limit",
            "side": "buy",
            "price": 10,
            "qty": 1,
            "id": "init_1",
            "user_id": "market_maker",
            "market_id": {"target_user_id": "alice", "threshold_minutes": 60},
        }
        resp = send_request(s, req)
        print(f"Response: {resp}")

        # 2. Ask what markets exist
        print("Listing markets...")
        resp = send_request(s, {"type": "get_markets"})
        print(f"Markets: {resp}")

        # Add assertions here based on expected behavior
        # For example:
        # assert "markets" in resp
        # assert len(resp["markets"]) > 0

    finally:
        s.close()
