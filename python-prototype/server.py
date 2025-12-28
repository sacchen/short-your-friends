import asyncio
import json
import os
import traceback
from decimal import Decimal
from typing import Any, Union

from orderbook.economy import EconomyManager
from orderbook.engine import MatchingEngine
from orderbook.id_mapper import UserIdMapper
from orderbook.types import (
    ActionResponse,
    SettlementResponse,
    SnapshotResponse,
)

# --- Configuration & Types ---

# Set to False during stress tests to save CPU cycles
DEBUG_MODE = True
DB_FILE = "state.json"
ResponseTypes = Union[
    ActionResponse, SnapshotResponse, SettlementResponse, dict[str, Any]
]


class DecimalEncoder(json.JSONEncoder):
    """Prevents 'Object of type Decimal is not JSON serializable' crash."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


# --- Server Logic ---


class OrderBookServer:
    """
    Asyncio-based order book server handling multiple concurrent connections.
    Each client connection runs in its own task with shared state (engine, economy, mapper).
    """

    def __init__(self):
        self.engine = MatchingEngine()
        self.economy = EconomyManager()
        self.user_id_mapper = UserIdMapper()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Runs once for every connection.
        10 concurrent versions if 10 people connect.
        """
        addr = writer.get_extra_info("peername")
        if DEBUG_MODE:
            print(f"[+] New connection from {addr}")

        try:
            while True:
                # Wait for data (ending in \n)
                try:
                    data = await reader.readuntil(b"\n")
                    if not data:
                        break
                except (
                    asyncio.IncompleteReadError,
                    ConnectionResetError,
                    BrokenPipeError,
                ):
                    break  # Client closed connection or bot disconnected

                message = data.decode().strip()
                if not message:
                    continue  # Ignore empty lines/pings

                # Parse JSON
                try:
                    request = json.loads(message)
                except json.JSONDecodeError:
                    if DEBUG_MODE:
                        print(f"[!] Invalid JSON from {addr}: {message[:50]}")
                    continue

                # Dispatch request to handler
                resp = await self.process_request(request, addr)

                # Write response
                writer.write((json.dumps(resp, cls=DecimalEncoder) + "\n").encode())
                await writer.drain()

        except Exception as e:
            print(f"[!] Connection Error with {addr}: {e}")
            if DEBUG_MODE:
                traceback.print_exc()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
            if DEBUG_MODE:
                print(f"[-] Client {addr} disconnected.")

    async def process_request(self, request: dict, addr: Any) -> ResponseTypes:
        """Route the request type to the appropriate handler logic."""
        req_type = request.get("type")
        if DEBUG_MODE:
            print(f"[{addr}] Request: {req_type}")

        try:
            match req_type:
                case "ping":
                    return {"type": "pong", "status": "ok"}

                case "proof_of_walk":
                    return self._handle_proof_of_walk(request)

                case "balance":
                    return self._handle_balance(request)

                case "place_order":
                    return await self._handle_place_order(request, addr)

                case "cancel":
                    return self._handle_cancel(request)

                case "read":
                    return self._handle_read(request)

                case "settle":
                    return self._handle_settle(request)

                case "get_markets":
                    return self._handle_get_markets()

                case _:
                    return {"status": "error", "message": "Unknown type"}

        except KeyError as e:
            if DEBUG_MODE:
                print(f"[!] Missing field in request from {addr}: {e}")
            return {"status": "error", "message": f"Missing field: {e}"}

        except Exception as e:
            print(f"[{addr}] Unexpected Logic Error: {e}")
            if DEBUG_MODE:
                traceback.print_exc()
            return {"status": "error", "message": "Internal server error"}

    # --- Request Handlers ---

    def _handle_proof_of_walk(self, req: dict) -> dict:
        """Economy & Health Endpoint: Process proof of walk for iOS client."""
        user_id = req["user_id"]
        steps = int(req["steps"])

        minted = self.economy.process_proof_of_walk(user_id, steps)
        new_balance = self.economy.get_account(user_id).balance_available

        return {
            "status": "ok",
            "minted": str(minted),
            "new_balance": str(new_balance),
        }

    def _handle_balance(self, req: dict) -> dict:
        """Return user's balance and portfolio positions."""
        user_id = req["user_id"]
        account = self.economy.get_account(user_id)

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

        return {
            "status": "ok",
            "user_id": user_id,
            "available": str(account.balance_available),
            "locked": str(account.balance_locked),
            "total_equity": str(account.total_equity()),
            "positions": positions_list,
        }

    async def _handle_place_order(self, req: dict, addr: Any) -> dict:
        """
        Place an order in the matching engine.

        Market ID Format: "alice_480" or "alice,480" -> (internal_id, 480)
        FIX: Always convert username to internal ID for engine to prevent
        duplicate markets (e.g., "alice" vs internal ID "1").
        """
        user_id_str = str(req["user_id"])
        side = req["side"]
        price_decimal = Decimal(str(req["price"])) / 100
        qty = int(req["qty"])

        try:
            # Parse Market ID (String "alice_480" -> Tuple (internal_id, 480))
            # Use rsplit to handle usernames that might contain underscores
            raw_market_id = req["market_id"]
            if "_" in raw_market_id:
                target_user, minutes_str = raw_market_id.rsplit("_", 1)
            else:
                # Fallback if we change ID format later
                target_user, minutes_str = raw_market_id.split(",")

            # FIX: Always convert username to internal ID for engine
            # This prevents duplicate markets (eg "alice" vs "1")
            target_user_int = self.user_id_mapper.to_internal(target_user)
            market_id = (target_user_int, int(minutes_str))

            # Engine uses prices in cents (integers)
            price_int = int(req["price"])
            order_id_int = int(req.get("id", 0))

            # Economy Check: Lock funds for Buy orders
            if side == "buy":
                if not self.economy.attempt_order_lock(user_id_str, price_decimal, qty):
                    error_msg = f"Insufficient funds. Need ${price_decimal * qty:.2f}"
                    print(f"[{addr}] Order Rejected: {error_msg}")
                    return {"status": "error", "message": error_msg}

            # Map string username to internal integer ID
            user_id_int = self.user_id_mapper.to_internal(user_id_str)

            # Create market if it doesn't exist
            if market_id not in self.engine._markets:
                market_name = f"{target_user} Sleep {int(minutes_str) // 60}:{int(minutes_str) % 60:02d}"
                self.engine.create_market(market_id, market_name)

            # Execute order in matching engine
            trades = self.engine.process_order(
                market_id=market_id,
                side=side,
                price=price_int,
                quantity=qty,
                order_id=order_id_int,
                user_id=user_id_int,
            )

            # Settlement: Confirm any resulting trades in economy
            for trade in trades:
                buyer_str = self.user_id_mapper.to_external(trade.buy_user_id)
                seller_str = self.user_id_mapper.to_external(trade.sell_user_id)

                # FIX: Use original username string, not internal ID
                # We need consistent string key for the portfolio dictionary
                mid_str = f"{target_user},{int(minutes_str)}"

                # Convert cents to dollars (Engine uses cents, Economy uses dollars)
                price_in_dollars = Decimal(trade.price) / 100

                self.economy.confirm_trade(
                    buyer_id=buyer_str,
                    seller_id=seller_str,
                    market_id=mid_str,
                    price=price_in_dollars,
                    quantity=trade.quantity,
                )

            # Price Improvement: Release unused locked funds
            # If buyer got a better price than they locked for, refund the difference
            if side == "buy" and len(trades) > 0:
                locked_price = price_decimal  # What they locked at (their order price)
                actual_price = Decimal(trades[0].price) / 100  # What they actually paid

                if actual_price < locked_price:
                    price_difference = locked_price - actual_price
                    self.economy.release_order_lock(
                        user_id_str, price_difference, trades[0].quantity
                    )
                    if DEBUG_MODE:
                        print(
                            f"[{addr}] Price Improvement: Refunded ${price_difference * trades[0].quantity:.2f}"
                        )

            print(f"[{addr}] Order Placed. Trades executed: {len(trades)}")
            return {
                "status": "ok",
                "message": "Order placed successfully",
                "trades": len(trades),
            }

        except ValueError as e:
            # If the engine rejects it (e.g., "Market Closed"), unlock the funds
            if side == "buy":
                self.economy.release_order_lock(user_id_str, price_decimal, qty)
            print(f"[{addr}] Engine Error: {e}")
            return {"status": "error", "message": str(e)}

    def _handle_cancel(self, req: dict) -> dict:
        """
        Cancel an order and release any locked funds.

        TODO: Optimize - currently searches all markets.
        Need to track market_id with each order for faster lookup.
        """
        order_id = req["id"]
        cancelled_order = None
        cancelled_side = None  # OrderNode doesn't store side, track separately

        # Search all markets for the order
        # TODO: optimize by storing market_id with order
        for market_id, book in self.engine._markets.items():
            if order_id in book._orders:
                order = book._orders[order_id]

                # Determine side by checking which book it's in
                if order.price in book._bids:
                    cancelled_side = "buy"
                elif order.price in book._asks:
                    cancelled_side = "sell"

                book.cancel_order(order_id)
                cancelled_order = order
                break

        if cancelled_order:
            # Refund: Release lock if it was a buy order
            if cancelled_side == "buy":
                # Convert internal ID back to string for Economy
                user_id_str = self.user_id_mapper.to_external(cancelled_order.user_id)
                self.economy.release_order_lock(
                    user_id=user_id_str,
                    price=Decimal(cancelled_order.price) / 100,
                    quantity=cancelled_order.quantity,
                )
            return {"status": "cancelled", "message": "Funds released"}

        return {"status": "error", "message": "Order not found"}

    def _handle_read(self, req: dict) -> SnapshotResponse:
        """
        Return order book snapshot.

        TODO: Need market_id in ReadBookRequest.
        Currently returns first market as fallback.
        """
        if not self.engine._markets:
            return SnapshotResponse(status="ok", bids=[], asks=[])

        # Get first market (will want to specify market_id later)
        first_market_id = next(iter(self.engine._markets.keys()))
        snap = self.engine.get_market_snapshot(first_market_id)

        return SnapshotResponse(status="ok", bids=snap["bids"], asks=snap["asks"])

    def _handle_settle(self, req: dict) -> dict:
        """
        Snitch command: iOS app reports actual screentime.
        Settles all markets for the target user based on actual outcome.
        """
        target_user_id = req["target_user_id"]
        actual_screentime_minutes = req["actual_screentime_minutes"]

        # FIX: Convert string username to internal ID for comparison
        target_user_int = self.user_id_mapper.to_internal(target_user_id)

        all_trades = []
        markets_settled = 0

        # Loop through markets to find those belonging to target user
        for market_id in list(self.engine._markets.keys()):
            if market_id[0] == target_user_int:  # Compare internal IDs
                threshold = market_id[1]
                # Terminal price: 1 if they met/exceeded threshold, 0 if not
                terminal_price = 1 if actual_screentime_minutes >= threshold else 0

                trades = self.engine._markets[market_id].settle_market(terminal_price)

                # FIX: Convert internal ID back to username string for economy
                target_user_str = self.user_id_mapper.to_external(market_id[0])
                mid_str = f"{target_user_str},{market_id[1]}"

                # Settle: Confirm trades in Economy with market_id
                for trade in trades:
                    buyer_str = self.user_id_mapper.to_external(trade.buy_user_id)
                    seller_str = self.user_id_mapper.to_external(trade.sell_user_id)

                    self.economy.confirm_trade(
                        buyer_id=buyer_str,
                        seller_id=seller_str,
                        market_id=mid_str,
                        price=Decimal(trade.price) / 100,
                        quantity=trade.quantity,
                    )

                all_trades.extend(trades)
                markets_settled += 1

        return {
            "status": "settled",
            "markets_settled": markets_settled,
            "total_trades": len(all_trades),
        }

    def _handle_get_markets(self) -> dict:
        """
        Return list of active markets with proper username conversion.

        Converts internal ID (1) back to username string ("alice") for client display.
        """
        raw_markets = self.engine.get_active_markets()
        clean_markets = []

        for m in raw_markets:
            try:
                # Parse the market ID to extract internal ID and convert back to username
                raw_id = str(m["id"])

                # Handle both "," and "_" separators
                sep = "," if "," in raw_id else "_"
                internal_id_str, minutes = raw_id.split(sep, 1)

                # CONVERT BACK: Int(1) -> Str("alice")
                real_username = self.user_id_mapper.to_external(int(internal_id_str))

                # Rebuild the ID with real username
                clean_m = m.copy()
                clean_m["id"] = f"{real_username},{minutes}"
                clean_markets.append(clean_m)

            except Exception:
                # Fallback if parsing fails
                clean_markets.append(m)

        return {"status": "ok", "markets": clean_markets}

    # --- Persistence ---

    def save_world(self) -> None:
        """Save engine, economy, and mapper state to JSON."""
        print("[*] Saving world state...")

        engine_state = self.engine.dump_state()
        economy_state = self.economy.dump_state()
        mapper_state = self.user_id_mapper.dump_state()

        # Convert Tuple keys in markets to Strings for JSON
        # Engine uses keys like (1, 60) that JSON cannot serialize
        if "markets" in engine_state:
            str_key_markets = {}
            for k, v in engine_state["markets"].items():
                if isinstance(k, tuple):
                    # Convert (1, 60) -> "1,60"
                    key_str = f"{k[0]},{k[1]}"
                    str_key_markets[key_str] = v
                else:
                    str_key_markets[k] = v
            engine_state["markets"] = str_key_markets

        data = {
            "economy": economy_state,
            "engine": engine_state,
            "mapper": mapper_state,
        }

        try:
            with open(DB_FILE, "w") as f:
                json.dump(data, f, indent=2, cls=DecimalEncoder)
            print("[*] Save complete.")
        except Exception as e:
            print(f"[!] SAVE FAILED: {e}")

    def load_world(self) -> None:
        """Load engine, economy, and mapper state from JSON."""
        if not os.path.exists(DB_FILE):
            print("[*] No save file found. Starting fresh.")
            return

        print("[*] Loading world state...")
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)

            if "economy" in data:
                self.economy.load_state(data["economy"])

            if "mapper" in data:
                self.user_id_mapper.load_state(data["mapper"])

            if "engine" in data:
                # Engine.load_state handles "1,60" string parsing internally
                self.engine.load_state(data["engine"])

            print(
                f"[*] Loaded {len(self.economy.accounts)} accounts and {len(self.engine._markets)} markets."
            )

        except Exception as e:
            print(f"[!] Failed to load save file: {e}")
            traceback.print_exc()

    def seed_dev_data(self) -> None:
        """Seed initial market data for development."""
        if self.engine._markets:
            return  # Already have markets

        print("[+] Seeding Dev Data...")

        # Fund the market maker (they need capital to provide liquidity)
        self.economy.get_account("market_maker").balance_available = Decimal("1000.00")
        print("[+] Funded market_maker with $1000.00")

        # Define Market ID - Convert string user ID to internal
        alice_internal_id = self.user_id_mapper.to_internal("alice")
        mm_id = self.user_id_mapper.to_internal("market_maker")
        m_id = (alice_internal_id, 480)

        # Create Market
        self.engine.create_market(m_id, "Alice Sleep 8:00 AM")

        # Place Seed Orders (Prices in Cents)
        # Buy 10 contracts at $0.40 (costs $4.00)
        if self.economy.attempt_order_lock("market_maker", Decimal("0.40"), 10):
            self.engine.process_order(
                market_id=m_id,
                side="buy",
                price=40,
                quantity=10,
                order_id=1,
                user_id=mm_id,
            )
            print("[+] Placed market maker buy: 10 @ $0.40")

        # Sell 10 contracts at $0.60 (sellers don't lock cash)
        self.engine.process_order(
            market_id=m_id,
            side="sell",
            price=60,
            quantity=10,
            order_id=2,
            user_id=mm_id,
        )
        print("[+] Placed market maker sell: 10 @ $0.60")

        print("[+] Seeding Complete: Added 'Alice Sleep 8:00 AM'")


# --- Background Tasks ---


async def periodic_save(server: OrderBookServer, interval: int = 300) -> None:
    """Periodically save world state every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        server.save_world()


# --- Main Entry Point ---


async def main() -> None:
    """Start the order book server and background tasks."""
    server = OrderBookServer()
    server.load_world()
    server.seed_dev_data()

    # Start TCP server
    tcp_server = await asyncio.start_server(server.handle_client, "0.0.0.0", 8888)

    addrs = ", ".join(str(sock.getsockname()) for sock in tcp_server.sockets)
    print(f"[*] Serving on {addrs}")

    # Run server and periodic save concurrently
    async with tcp_server:
        await asyncio.gather(
            tcp_server.serve_forever(),
            periodic_save(server),
        )


if __name__ == "__main__":
    server_instance = None
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Stopping server...")
        # Note: server_instance is not accessible here in the finally block
        # Save is handled by periodic_save during normal operation
        # For production, consider signal handlers for graceful shutdown
        print("[!] Server stopped.")
