# Usage: PYTHONPATH=src uv run trigger_settle.py

import asyncio
import json
import sys
from typing import Final, TypedDict

# Config
HOST: Final[str] = "127.0.0.1"
PORT: Final[int] = 8888


# Type Defs
class SettleRequest(TypedDict):
    """
    Strict typing for the 'Snitch' payload.
    """

    type: str
    target_user_id: int
    actual_screentime_minutes: int


# Snitch
async def main() -> None:
    print("[*] [iOS Client] Background task woke up...")

    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
    except ConnectionRefusedError:
        print("[!] Could not connect to the Exchange. Is server.py running?")
        sys.exit(1)

    # Construct Truth
    # Later: this data comes from Apple's ScreenTime API
    payload: SettleRequest = {
        "type": "settle",
        "target_user_id": 1,  # The ID for "Sam"
        "actual_screentime_minutes": 120,  # [!] 2 hours! (Over the 60m limit)
    }

    print(
        f"[!] [Oracle] Reporting violation: {payload['actual_screentime_minutes']} minutes used."
    )

    # Send Data (NDJSON)
    message = json.dumps(payload) + "\n"
    writer.write(message.encode())
    await writer.drain()

    # Get Confirmation
    # Server will return how many trades were liquidated
    data = await reader.readuntil(b"\n")
    response = json.loads(data.decode())

    # Report Result
    if response.get("status") == "settled":
        print("\n[!] MARKET COLLAPSED")
        print(f"Target User: {payload['target_user_id']}")
        print(f"Markets Closed: {response.get('markets_settled')}")
        print(f"Positions Liquidated: {response.get('total_trades')}")
        print("-" * 30)
        print("All long positions are now worth $0.00.")
        print("All short positions are now worth $1.00.")
    else:
        print(f"[!] Unexpected response: {response}")

    writer.close()
    await writer.wait_closed()


if __name__ == "__main__":
    try:
        # Windows compatibility for asyncio
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
