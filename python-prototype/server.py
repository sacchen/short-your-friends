# Usage: PYTHONPATH=src uv run server.py

import asyncio
import json
from typing import Any, Union

# from orderbook.book import OrderBook
from orderbook.engine import MarketId, MatchingEngine
from orderbook.types import (
    ActionResponse,
    LimitOrderRequest,
    SettleMarketRequest,
    SettlementResponse,
    SnapshotResponse,
)

# Union type helper
ResponseTypes = Union[
    ActionResponse, SnapshotResponse, SettlementResponse, dict[str, Any]
]

# Global instance (Shared Memory)
# market = OrderBook()
engine = MatchingEngine()


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
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

                # resp: dict[str, Any] | SnapshotResponse
                resp: ResponseTypes

                # Switchboard (Routing logic to Engine)
                if request["type"] == "limit":
                    # Need auth/session in future
                    # user_id = int(request.get("user_id", 0))
                    limit_req: LimitOrderRequest = request

                    # Extract market_id from request
                    market_id_dict = limit_req["market_id"]
                    market_id: MarketId = (
                        market_id_dict["target_user_id"],
                        market_id_dict["threshold_minutes"],
                    )

                    # Process order (matches immediately if possible)
                    trades = engine.process_order(
                        market_id=market_id,
                        side=limit_req["side"],
                        price=limit_req["price"],
                        quantity=limit_req["qty"],
                        order_id=limit_req["id"],
                        user_id=limit_req["user_id"],
                    )

                    resp = {
                        "status": "accepted",
                        "message": f"Order placed, {len(trades)} trades executed",
                    }

                    # market.add_order(
                    #     side=request["side"],
                    #     price=request["price"],
                    #     quantity=request["qty"],
                    #     order_id=request["id"],
                    #     user_id=user_id,
                    # )
                    # resp = {"status": "accepted"}

                elif request["type"] == "cancel":
                    # TODO: Need to know which market this order is in
                    # Right now: search all markets
                    order_id = request["id"]
                    cancelled = False
                    for market_id, book in engine._markets.items():
                        if order_id in book._orders:
                            book.cancel_order(order_id)
                            cancelled = True
                            break

                    resp = {
                        "status": "cancelled" if cancelled else "error",
                        "message": "Order not found" if not cancelled else "",
                    }

                    # market.cancel_order(request["id"])
                    # resp = {"status": "cancelled"}

                elif request["type"] == "read":
                    # TODO: Which market to read? For now, return first market
                    # In production: need market_id in ReadBookRequest

                    if not engine._markets:
                        resp = SnapshotResponse(
                            status="ok",
                            bids=[],
                            asks=[],
                        )
                    else:
                        # Get first market (you'll want to specify market_id later)
                        first_market_id = next(iter(engine._markets.keys()))
                        snap = engine.get_market_snapshot(first_market_id)

                        resp = SnapshotResponse(
                            status="ok",
                            bids=snap["bids"],
                            asks=snap["asks"],
                        )

                    # format engine data to match SnapshotResponse
                    # snap = market.snapshot()  # returns {"bids": ..., "asks": ...}

                    # # Construct typed response
                    # resp = SnapshotResponse(
                    #     status="ok",
                    #     bids=snap["bids"],
                    #     asks=snap["asks"],
                    # )
                elif request["type"] == "settle":
                    # Snitch command: iOS app reports actual screentime
                    settle_req: SettleMarketRequest = request

                    all_trades = engine.settle_markets_for_user(
                        target_user_id=settle_req["target_user_id"],
                        actual_screentime_minutes=settle_req[
                            "actual_screentime_minutes"
                        ],
                    )

                    resp = {
                        "status": "settled",
                        "markets_settled": len(
                            [
                                m
                                for m in engine._markets.keys()
                                if m[0] == settle_req["target_user_id"]
                            ]
                        ),
                        "total_trades": len(all_trades),
                    }

                else:
                    resp = {
                        "status": "error",
                        "message": f"Unknown request type: {request.get('type')}",
                    }

                # Send back
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()

            except KeyError as e:
                # Catches if client sends {"type": "limit"} but not "price"
                err = {"status": "error", "message": f"Missing field: {e}"}
                writer.write((json.dumps(err) + "\n").encode())
                await writer.drain()

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
        import traceback

        traceback.print_exc()
    finally:
        writer.close()
        await writer.wait_closed()


async def main() -> None:
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
