# tests/test_persistence.py
# Usage:
#   Start server: PYTHONPATH=src uv run server.py
#   Create user_1:uv run pytest tests/test_integration.py
#   Stop server
#   Restart server
#   Run test:     uv run pytest tests/test_persistence.py

import json
import socket

import pytest


def send_request(sock, request_dict):
    """Helper to send JSON and get JSON response"""
    msg = json.dumps(request_dict).encode() + b"\n"
    sock.sendall(msg)

    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Server closed connection")
        data += chunk

    return json.loads(data.decode().strip())


def test_persistence():
    """Test that server persists user balance across restarts"""
    # host = "127.0.0.1"
    host = "REDACTED_IP"
    port = 8888

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
    except ConnectionRefusedError:
        pytest.skip(
            f"Server not running at {host}:{port}. Start with: PYTHONPATH=src uv run server.py"
        )

    try:
        print("Checking if server remembers test_user_1...")
        response = send_request(s, {"type": "balance", "user_id": "test_user_1"})

        print(f"Server Memory: {response}")

        # Assert that the total equity persisted (should be 100.00 if test_integration ran first)
        # Note: available might be less if there are locked orders, but total_equity should persist
        assert response.get("total_equity") == "100.00", (
            f"The money did not survive the restart! Got total_equity: {response.get('total_equity')}"
        )

        print("[+] SUCCESS: The money survived the restart!")
        print(
            f"   Available: {response.get('available')}, Locked: {response.get('locked')}, Total: {response.get('total_equity')}"
        )

    finally:
        s.close()
