import asyncio
import json
import os
from decimal import Decimal
from typing import Any, Union

from orderbook.economy import EconomyManager
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

                elif request["type"] == "balance":
                    # {"type": "balance", "user_id": "alice"}
                    user_id = request["user_id"]
                    account = economy.get_account(user_id)

                    # Format Portfolio for Swift Client
                    positions_list = []
                    for m_id, qty in account.portfolio.items():
                        if qty != 0:
                            positions_list.append(
                                {
                                    "market_id": m_id,
                                    "side": "LONG" if qty > 0 else "SHORT",
                                    "qty": abs(qty),
                                    "average_price": 0.0,  # Placeholder
                                }
                            )

                    resp = {
                        "status": "ok",
                        "user_id": user_id,
                        "available": str(account.balance_available),
                        "locked": str(account.balance_locked),
                        "total_equity": str(account.total_equity()),
                        "positions": positions_list,
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

                        # FIX: Always convert username to internal ID for engine
                        # This prevents duplicate markets (eg "alice" vs "1")
                        target_user_int = user_id_mapper.to_internal(target_user)
                        market_id = (target_user_int, int(minutes_str))

                        # Extract Order Details
                        user_id_str = str(request["user_id"])
                        side = request["side"]
                        price_int = int(request["price"])  # Engine uses Int (cents)
                        price_decimal = (
                            Decimal(str(request["price"])) / 100
                        )  # Economy uses Dollars
                        qty = int(request["qty"])
                        order_id_int = int(request.get("id", 0))  # Convert to int

                        # Economy Check: Lock funds for Buys
                        if side == "buy":
                            # attempt_order_lock expects string ID and Decimal price
                            if not economy.attempt_order_lock(
                                user_id_str, price_decimal, qty
                            ):
                                error_msg = f"Insufficient funds. Need ${price_decimal * qty:.2f}"
                                print(f"[{addr}] Order Rejected: {error_msg}")
                                resp = {"status": "error", "message": error_msg}
                                writer.write((json.dumps(resp) + "\n").encode())
                                await writer.drain()
                                continue

                        # Execute in Matching Engine
                        # Map "test_user_1" -> 2 (Internal Integer ID)
                        user_id_int = user_id_mapper.to_internal(user_id_str)

                        if market_id not in engine._markets:
                            market_name = f"{target_user} Sleep {int(minutes_str) // 60}:{int(minutes_str) % 60:02d}"
                            engine.create_market(market_id, market_name)

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

                            # Use market_id string (eg "alice_480" or "alice,480")
                            # We need consistent string key for the portfolio dictionary
                            # FIX: Use original username string, not internal ID
                            mid_str = f"{target_user},{int(minutes_str)}"

                            # Convert cents to dollars
                            # Engine returns cents. Economy expects dollars
                            price_in_dollars = Decimal(trade.price) / 100

                            economy.confirm_trade(
                                buyer_id=buyer_str,
                                seller_id=seller_str,
                                market_id=mid_str,
                                price=price_in_dollars,
                                quantity=trade.quantity,
                            )

                        # Price Improvement: Release unused locked funds
                        # If buyer got a better price than they locked for, refund the difference
                        if side == "buy" and len(trades) > 0:
                            # What they locked at (their order price)
                            locked_price = price_decimal

                            # What they actually paid (execution price from first trade)
                            # In multi-trade scenarios, this handles the first fill
                            actual_price = Decimal(trades[0].price) / 100

                            if actual_price < locked_price:
                                price_difference = locked_price - actual_price
                                economy.release_order_lock(
                                    user_id_str, price_difference, trades[0].quantity
                                )
                                print(
                                    f"[{addr}] Price Improvement: Refunded ${price_difference * trades[0].quantity:.2f}"
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
                                Decimal(str(request["price"])) / 100,
                                int(request["qty"]),
                            )

                        print(f"[{addr}] Engine Error: {e}")
                        resp = {"status": "error", "message": str(e)}

                    except Exception as e:
                        print(f"[{addr}] Unexpected Error: {e}")
                        import traceback

                        traceback.print_exc()
                        resp = {"status": "error", "message": "Internal server error"}

                elif request["type"] == "cancel":
                    # TODO: Need to know which market this order is in
                    # Right now: search all markets
                    order_id = request["id"]
                    cancelled_order = None
                    cancelled_side = (
                        None  # Track side separately. OrderNode doesn't store it
                    )

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
                                user_id=user_id_str,
                                price=Decimal(cancelled_order.price) / 100,
                                quantity=cancelled_order.quantity,
                            )

                        resp = {"status": "cancelled", "message": "Funds released"}
                    else:
                        resp = {"status": "error", "message": "Order not found"}

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

                elif request["type"] == "settle":
                    # Snitch command: iOS app reports actual screentime
                    settle_req: SettleMarketRequest = request
                    target_user_id = settle_req["target_user_id"]
                    actual_screentime_minutes = settle_req["actual_screentime_minutes"]

                    # FIX: Convert string username to internal ID for comparison
                    target_user_int = user_id_mapper.to_internal(target_user_id)

                    all_trades = []
                    markets_settled = 0

                    # Loop through markets to track which market_id each trade came from
                    for market_id in list(engine._markets.keys()):
                        if market_id[0] == target_user_int:  # Compare internal IDs
                            threshold = market_id[1]
                            terminal_price = (
                                1 if actual_screentime_minutes >= threshold else 0
                            )
                            trades = engine._markets[market_id].settle_market(
                                terminal_price
                            )

                            # Convert market_id tuple to string format for economy
                            # FIX: Convert internal ID back to username string
                            target_user_str = user_id_mapper.to_external(market_id[0])
                            mid_str = f"{target_user_str},{market_id[1]}"

                            # Settle: Confirm trades in Economy with market_id
                            for trade in trades:
                                buyer_str = user_id_mapper.to_external(
                                    trade.buy_user_id
                                )
                                seller_str = user_id_mapper.to_external(
                                    trade.sell_user_id
                                )
                                economy.confirm_trade(
                                    buyer_id=buyer_str,
                                    seller_id=seller_str,
                                    market_id=mid_str,
                                    price=Decimal(trade.price) / 100,
                                    quantity=trade.quantity,
                                )

                            all_trades.extend(trades)
                            markets_settled += 1

                    resp = {
                        "status": "settled",
                        "markets_settled": markets_settled,
                        "total_trades": len(all_trades),
                    }

                elif request["type"] == "get_markets":
                    # Get raw markets from engine (Uses Int ID: (1, 480))
                    raw_markets = engine.get_active_markets()

                    clean_markets = []

                    for m in raw_markets:
                        # m is a dict like {"id": "1,480", "name": "..."}
                        # We need to parse the ID to fix the username

                        # Handle tuple or string id
                        # The engine might return the tuple key directly or a string representation
                        # Let's handle the string "1,480" which seems to be what you get
                        try:
                            raw_id = str(m["id"])
                            if "," in raw_id:
                                internal_id_str, minutes = raw_id.split(",")
                            elif "_" in raw_id:
                                internal_id_str, minutes = raw_id.split("_")
                            else:
                                # Can't parse, just keep original
                                clean_markets.append(m)
                                continue

                            internal_id = int(internal_id_str)

                            # CONVERT BACK: Int(1) -> Str("alice")
                            real_username = user_id_mapper.to_external(internal_id)

                            # Rebuild the ID: "alice,480"
                            new_id = f"{real_username},{minutes}"

                            # Create a clean copy of the market object
                            clean_m = m.copy()
                            clean_m["id"] = new_id
                            clean_markets.append(clean_m)

                        except Exception:
                            # Fallback if parsing fails
                            clean_markets.append(m)

                    resp = {"status": "ok", "markets": clean_markets}

                else:
                    resp = {"status": "error", "message": "Unknown type"}

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
    # local:
    # server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)
    # actual server:
    server = await asyncio.start_server(handle_client, "0.0.0.0", 8888)

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

            # Fund the market maker
            # Market makers need capital to provide liquidity
            economy.get_account("market_maker").balance_available = Decimal("1000.00")
            print("[+] Funded market_maker with $1000.00")

            # Define Market ID - Convert string user ID to internal
            alice_internal_id = user_id_mapper.to_internal("alice")
            m_id = (alice_internal_id, 480)

            # Create Market
            engine.create_market(m_id, "Alice Sleep 8:00 AM")

            # Create generic Market Maker user
            mm_id = user_id_mapper.to_internal("market_maker")

            # Place Seed Orders (Prices in Cents)
            # These will now properly lock funds through the economy system

            # Buy 10 contracts at $0.40 (costs $4.00)
            # Lock funds for buy order
            if economy.attempt_order_lock("market_maker", Decimal("0.40"), 10):
                engine.process_order(
                    market_id=m_id,
                    side="buy",
                    price=40,
                    quantity=10,
                    order_id=1,
                    user_id=mm_id,
                )
                print("[+] Placed market maker buy: 10 @ $0.40")

            # Sell 10 contracts at $0.60
            # Sellers don't lock cash, so just place the order
            engine.process_order(
                market_id=m_id,
                side="sell",
                price=60,
                quantity=10,
                order_id=2,
                user_id=mm_id,
            )
            print("[+] Placed market maker sell: 10 @ $0.60")

            print("[+] Seeding Complete: Added 'Alice Sleep 8:00 AM'")

        # Run event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Stopping server...")
        save_world()
        print("[!] Server stopped.")
