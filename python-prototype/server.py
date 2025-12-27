# Usage: PYTHONPATH=src uv run server.py
# To test JSON saving,
# run server, run test_integration.py, stop server,
# check state.json, start server
# uv run pytest tests/test_integration.py

# in terminal. to place buy order for 5 shares at 41 cents
# echo '{"type": "place_order", "market_id": "alice_480", "user_id": "test_user_1", "side": "buy", "price": 41, "qty": 5, "id": 999}' | nc localhost 8888
# buy 2 contracts at 60 cents
# echo '{"type": "place_order", "market_id": "alice_480", "user_id": "test_user_1", "side": "buy", "price": 60, "qty": 2, "id": 1002}' | nc localhost 8888

# trade executed, but state did not update

import asyncio
import json
import os
from decimal import Decimal
from typing import Any, Union

from orderbook.economy import EconomyManager

# from orderbook.book import OrderBook
from orderbook.engine import MatchingEngine
from orderbook.id_mapper import UserIdMapper
from orderbook.types import (
    ActionResponse,
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
economy = EconomyManager()
user_id_mapper = UserIdMapper()


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

                # Economy & Health Endpoints for Swift Client
                if request["type"] == "proof_of_walk":
                    # {"type:": "proof_of_walk", "user_id": "alice", "steps": 5000}
                    user_id = request["user_id"]
                    steps = int(request["steps"])

                    minted = economy.process_proof_of_walk(user_id, steps)
                    new_balance = economy.get_account(user_id).balance_available

                    resp = {
                        "status": "ok",
                        "minted": str(minted),
                        "new_balance": str(new_balance),
                    }

                elif request["type"] == "place_order":
                    # Expects: {"type": "place_order", "market_id": "alice_480",
                    #           "user_id": "test_user_1", "side": "buy", "price": 40, "qty": 5}

                    try:
                        # Parse Market ID (String "alice_480" -> Tuple ("alice", 480))
                        # Use rsplit to handle usernames that might contain underscores
                        raw_market_id = request["market_id"]
                        if "_" in raw_market_id:
                            target_user, minutes_str = raw_market_id.rsplit("_", 1)
                        else:
                            # Fallback if we change ID format later
                            target_user, minutes_str = raw_market_id.split(",")

                        market_id = (target_user, int(minutes_str))

                        # Extract Order Details
                        user_id_str = str(request["user_id"])
                        side = request["side"]
                        price_int = int(request["price"])  # Engine uses Int (cents)
                        price_decimal = Decimal(str(request["price"])) / 100
                        qty = int(request["qty"])
                        order_id_int = int(request.get("id", 0))  # Convert to int

                        # Economy Check: Lock funds for Buys
                        if side == "buy":
                            # attempt_order_lock expects string ID and Decimal price
                            if not economy.attempt_order_lock(
                                user_id_str, price_decimal, qty
                            ):
                                error_msg = f"Insufficient funds. Need ${price_decimal * qty / 100:.2f}"
                                print(f"[{addr}] Order Rejected: {error_msg}")
                                resp = {"status": "error", "message": error_msg}
                                writer.write((json.dumps(resp) + "\n").encode())
                                await writer.drain()
                                continue

                        # Execute in Matching Engine
                        # Map "test_user_1" -> 2 (Internal Integer ID)
                        user_id_int = user_id_mapper.to_internal(user_id_str)

                        trades = engine.process_order(
                            market_id=market_id,
                            side=side,
                            price=price_int,
                            quantity=qty,
                            order_id=order_id_int,
                            user_id=user_id_int,
                        )

                        # Settlement: Confirm any resulting trades
                        for trade in trades:
                            buyer_str = user_id_mapper.to_external(trade.buy_user_id)
                            seller_str = user_id_mapper.to_external(trade.sell_user_id)
                            economy.confirm_trade(
                                buyer_id=buyer_str,
                                seller_id=seller_str,
                                price=Decimal(trade.price),
                                quantity=trade.quantity,
                            )

                        print(f"[{addr}] Order Placed. Trades executed: {len(trades)}")
                        resp = {
                            "status": "ok",
                            "message": "Order placed successfully",
                            "trades": len(trades),
                        }

                    except ValueError as e:
                        # If the engine rejects it (e.g. "Market Closed"), unlock the funds
                        if request["side"] == "buy":
                            economy.release_order_lock(
                                user_id_str,
                                Decimal(str(request["price"])),
                                int(request["qty"]),
                            )

                        print(f"[{addr}] Engine Error: {e}")
                        resp = {"status": "error", "message": str(e)}

                    except Exception as e:
                        print(f"[{addr}] Unexpected Error: {e}")
                        import traceback

                        traceback.print_exc()
                        resp = {"status": "error", "message": "Internal server error"}
                    # elif request["type"] == "balance":
                    #     # {"type": "balance", "user_id": "alice"}
                    #     user_id = request["user_id"]
                    #     account = economy.get_account(user_id)
                    #     resp = {
                    #         "status": "ok",
                    #         "user_id": user_id,
                    #         "available": str(account.balance_available),
                    #         "locked": str(account.balance_locked),
                    #         "total_equity": str(account.total_equity()),
                    #     }
                    # # Trading Logic with Economy Checks
                    # # Switchboard (Routing logic to Engine)
                    # elif request["type"] == "limit":
                    #     # Need auth/session in future
                    #     # user_id = int(request.get("user_id", 0))
                    #     limit_req: LimitOrderRequest = request

                    #     # Extract Data
                    #     user_id_str = str(limit_req["user_id"])
                    #     price = Decimal(str(limit_req["price"]))
                    #     qty = int(limit_req["qty"])
                    #     side = limit_req["side"]

                    #     # Check Funds for Buys
                    #     if side == "buy":
                    #         if not economy.attempt_order_lock(user_id_str, price, qty):
                    #             resp = {
                    #                 "status": "error",
                    #                 "message": f"Insufficient funds. Need {price * qty}",
                    #             }
                    #             # Send error and skip the rest
                    #             writer.write((json.dumps(resp) + "\n").encode())
                    #             await writer.drain()
                    #             continue

                    #     # Extract market_id from request
                    #     market_id_dict = limit_req["market_id"]
                    #     market_id: MarketId = (
                    #         market_id_dict["target_user_id"],
                    #         market_id_dict["threshold_minutes"],
                    #     )

                    #     try:
                    #         # Convert to internal ID for matching engine
                    #         user_id_int = user_id_mapper.to_internal(user_id_str)

                    #         # Process order (matches immediately if possible)
                    #         trades = engine.process_order(
                    #             # market_id=market_id,
                    #             # side=limit_req["side"],
                    #             # price=limit_req["price"],
                    #             # quantity=limit_req["qty"],
                    #             # order_id=limit_req["id"],
                    #             # user_id=limit_req["user_id"],
                    #             market_id=market_id,
                    #             side=side,
                    #             price=int(price),
                    #             quantity=qty,
                    #             order_id=limit_req["id"],
                    #             user_id=user_id_int,
                    #         )

                    #         # Settle: Confirm trades in Economy
                    #         for trade in trades:
                    #             buyer_str = user_id_mapper.to_external(trade.buy_user_id)
                    #             seller_str = user_id_mapper.to_external(trade.sell_user_id)
                    #             economy.confirm_trade(
                    #                 buyer_id=buyer_str,
                    #                 seller_id=seller_str,
                    #                 price=Decimal(trade.price),
                    #                 quantity=trade.quantity,
                    #             )

                    #         resp = {
                    #             "status": "accepted",
                    #             "message": f"Order placed, {len(trades)} trades executed",
                    #         }

                    #         # market.add_order(
                    #         #     side=request["side"],
                    #         #     price=request["price"],
                    #         #     quantity=request["qty"],
                    #         #     order_id=request["id"],
                    #         #     user_id=user_id,
                    #         # )
                    #         # resp = {"status": "accepted"}

                    # except ValueError as e:
                    #     # If engine rejects order (eg market closed),
                    #     # then we unlocked the funds that were just locked.
                    #     if side == "buy":
                    #         economy.release_order_lock(user_id, price, qty)

                    #     # Error Response (Market is Closed)
                    #     print(f"[{addr}] Rejected: {e}")
                    #     resp = {"status": "error", "message": str(e)}

                elif request["type"] == "cancel":
                    # TODO: Need to know which market this order is in
                    # Right now: search all markets
                    order_id = request["id"]
                    cancelled_order = None
                    cancelled_side = (
                        None  # Track side separately. OrderNode doesn't store it
                    )
                    # cancelled = False

                    # Search all markets
                    # TODO: optimize
                    for market_id, book in engine._markets.items():
                        if order_id in book._orders:
                            # Get order details before cancelling
                            # to know how much money to unlock.
                            order = book._orders[order_id]

                            # Determine side by checking which book it is in.
                            if order.price in book._bids:
                                cancelled_side = "buy"
                            elif order.price in book._asks:
                                cancelled_side = "sell"

                            book.cancel_order(order_id)
                            cancelled_order = order
                            break

                    if cancelled_order:
                        # Refund: Release lock if it was a buy order.
                        if cancelled_side == "buy":  # Using tracked side
                            # Convert internal ID back to string for Economy
                            user_id_str = user_id_mapper.to_external(
                                cancelled_order.user_id
                            )
                            economy.release_order_lock(
                                user_id=str(cancelled_order.user_id),
                                price=Decimal(cancelled_order.price),
                                quantity=cancelled_order.quantity,
                            )

                        resp = {"status": "cancelled", "message": "Funds released"}
                    else:
                        resp = {"status": "error", "message": "Order not found"}

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
                        # Get first market (will want to specify market_id later)
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

                    # Settle: Confirm trades in Economy
                    for trade in all_trades:
                        buyer_str = user_id_mapper.to_external(trade.buy_user_id)
                        seller_str = user_id_mapper.to_external(trade.sell_user_id)
                        economy.confirm_trade(
                            buyer_id=buyer_str,
                            seller_id=seller_str,
                            price=Decimal(trade.price),
                            quantity=trade.quantity,
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

                elif request["type"] == "get_markets":
                    # No params. Just list.
                    market_list = engine.get_active_markets()

                    resp = {"status": "ok", "markets": market_list}

                    # Debug: print json we're sending
                    # print(f"DEBUG OUTGOING JSON: {json.dumps(resp)}")

                else:
                    resp = {
                        "status": "error",
                        "message": f"Unknown request type: {request.get('type')}",
                    }

                # Send back
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()

            except KeyError as e:
                import traceback

                traceback.print_exc()
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


# Stop and load JSON when we start.

DB_FILE = "state.json"


def save_world() -> None:
    print("[*] Saving world state...")

    # Get raw state
    engine_state = engine.dump_state()
    economy_state = economy.dump_state()
    mapper_state = user_id_mapper.dump_state()

    # Convert Tuple keys in markets to Strings for JSON
    # Engine uses keys like ("alice", 60) that JSON can not use
    if "markets" in engine_state:
        str_key_markets = {}
        for k, v in engine_state["markets"].items():
            if isinstance(k, tuple):
                key_str = f"{k[0]},{k[1]}"  # Convert ("alice", 60) -> "alice,60"
                str_key_markets[key_str] = v
            else:
                str_key_markets[k] = v
        engine_state["markets"] = str_key_markets

    data = {"economy": economy_state, "engine": engine_state, "mapper": mapper_state}

    # Use custom encoder for Decimals (money)
    # Prevents "Object of type Decimal is not JSON serializable" crash
    class DecimalEncoder(json.JSONEncoder):
        def default(self, obj: Any) -> Any:
            if isinstance(obj, Decimal):
                return str(obj)
            return super().default(obj)

    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=2, cls=DecimalEncoder)
        print("[*] Save complete.")
    except Exception as e:
        print(f"[!] SAVE FAILED: {e}")


def load_world() -> None:
    if not os.path.exists(DB_FILE):
        print("[*] No save file found. Starting fresh.")
        return

    print("[*] Loading world state...")
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)

        if "economy" in data:
            economy.load_state(data["economy"])

        if "mapper" in data:
            user_id_mapper.load_state(data["mapper"])

        if "engine" in data:
            # We removed converting keys here. Pass raw data to engine.
            # Engine.load_state now handles the "alice,480" string parsing itself.

            engine.load_state(data["engine"])

        print(
            f"[*] Loaded {len(economy.accounts)} accounts and {len(engine._markets)} markets."
        )
    except Exception as e:
        print(f"[!] Failed to load save file: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    try:
        load_world()  # Load on start

        # Dev data: Seed market
        # Runs if database is empty
        if not engine._markets:
            print("[+] Seeding Dev Data...")

            # Define Market ID - Convert string user ID to internal
            alice_internal_id = user_id_mapper.to_internal("alice")
            m_id = (alice_internal_id, 480)

            # Create Market
            engine.create_market(m_id, "Alice Sleep 8:00 AM")

            # Create generic Market Maker user
            mm_id = user_id_mapper.to_internal("market_maker")

            # Place Seed Orders (Prices in Cents)
            # Buy 10 contracts at $0.40
            # order_id must be int, not string
            engine.process_order(
                market_id=m_id,
                side="buy",
                price=40,
                quantity=10,
                order_id=1,
                user_id=mm_id,
            )

            # Sell 10 contracts at $0.60
            engine.process_order(
                market_id=m_id,
                side="sell",
                price=60,
                quantity=10,
                order_id=2,
                user_id=mm_id,
            )

            print("[+] Seeding Complete: Added 'Alice Sleep 8:00 AM'")

        # Run event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Stopping server...")
        save_world()
        print("[!] Server stopped.")
