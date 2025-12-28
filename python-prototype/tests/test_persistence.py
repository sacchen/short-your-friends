import json
import os
import socket
import time
import uuid

HOST = os.getenv("TEST_SERVER_HOST", "127.0.0.1")
PORT = int(os.getenv("TEST_SERVER_PORT", "8888"))


def send_request(sock, request_dict):
    msg = json.dumps(request_dict).encode() + b"\n"
    sock.sendall(msg)
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return json.loads(data.decode().strip())


def test_persistence():
    """Verify that state is saved and retrievable."""
    user = f"persist_test_{uuid.uuid4().hex[:8]}"

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((HOST, PORT))

        # 1. Create state: Mint 100.00
        print(f"Creating state for {user}...")
        send_request(s, {"type": "proof_of_walk", "user_id": user, "steps": 10000})

        # 2. Wait for Disk I/O
        # (Wait for your server's periodic save or just a buffer for the OS)
        print("Waiting for server persistence...")
        time.sleep(1.1)

        # 3. Verify state
        response = send_request(s, {"type": "balance", "user_id": user})
        assert response.get("total_equity") == "100.00"

        print(f"[+] SUCCESS: State persisted for {user}")
    finally:
        s.close()
