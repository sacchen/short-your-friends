# Usage: PYTHONPATH=src uv run server.py

import asyncio
import json

from orderbook.types import SnapshotResponse
from src.orderbook.book import OrderBook

# Global instance (Shared Memory)
market = OrderBook()


async def handle_client(reader, writer):
    """
    This functions runs once from every connection.
    10 concurrent versions if 10 people connect.
    """

    # Get IP address of the person connecting
    addr = writer.get_extra_info("peername")
    print(f"[+] New connection from {addr}")

    try:
        while True:
            # Wait for data (ending in \n)
            data = await reader.readuntil(b"\n")

            # Parse JSON
            # Expect strings like: {"type": "limit", "side": "buy",
            #                       "price": 100, "qty": 10}
            try:
                message = data.decode().strip()
                if not message:
                    continue

                request = json.loads(message)
                print(f"[{addr}] Request: {request}")

                response = {}

                # Switchboard (Routing logic to Engine)
                if request["type"] == "limit":
                    market.add_order(
                        request["id"], request["side"], request["price"], request["qty"]
                    )
                    resp = {"status": "accepted"}

                elif request["type"] == "cancel":
                    market.cancel_order(request["id"])
                    resp = {"status": "cancelled"}

                elif request["type"] == "read":
                    # format engine data to match SnapshotResponse
                    snap = market.snapshot()

                    # Construct typed response
                    response: SnapshotResponse = {
                        "status": "ok",
                        "bids": snap["bids"],
                        "asks": snap["asks"],
                    }
                    resp = response

                # Send back
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()

            except KeyError as e:
                # Catches if client sends {"type": "limit"} but not "price"
                err = {"status": "error", "message": f"Missing field: {e}"}
                writer.write((json.dumps(err) + "\n").encode())

    except Exception as e:
        print(f"[-] Error: {e}")

        # BASIC LOGIC:
        # Wait for data
        # Looking for \n. Using Newline Delimited JSON
        # data = await reader.readuntil(b"\n")

        # Decode bytes -> string
        # message = data.decode().strip()
        # print(f"Received: {message}")

        # Echo: Send it back
        # response = f"Echo: {message}\n"
        # writer.write(response.encode())
        # await writer.drain()  # Makes sure buffer flushes to network

    except asyncio.IncompleteReadError:
        print(f"[-] Client {addr} disconnected.")
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def main():
    # Start server on localhost port 8888
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)

    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"[*] Serving on {addrs}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        # Run event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Server stopped.")
