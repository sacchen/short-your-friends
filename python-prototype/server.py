# python -m src.server

import asyncio
import json
import os
import traceback
from decimal import Decimal
from typing import Any

from engine.engine import MatchingEngine
from engine.interface import EngineInterface, translate_client_message
from orderbook.audit import SystemAuditor
from orderbook.economy import EconomyManager
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
ResponseTypes = ActionResponse, SnapshotResponse, SettlementResponse, dict[str, Any]


class DecimalEncoder(json.JSONEncoder):
    """Prevents 'Object of type Decimal is not JSON serializable' crash."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


# --- Server Logic ---


class OrderBookServer:
    """
    Asyncio-based order book server.
    Delegates logic to EngineInterface.
    """

    def __init__(self) -> None:
        self.economy = EconomyManager()
        self.engine = MatchingEngine()
        self.auditor = SystemAuditor(engine=self.engine, economy=self.economy)
        self.user_id_mapper = UserIdMapper()

        self.interface = EngineInterface(
            engine=self.engine,
            economy=self.economy,
            auditor=self.auditor,
            user_id_mapper=self.user_id_mapper,
            debug_mode=DEBUG_MODE,
        )

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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
            except (ConnectionResetError, asyncio.IncompleteReadError, OSError):
                pass
            if DEBUG_MODE:
                print(f"[-] Client {addr} disconnected.")

    async def process_request(self, request: dict[str, Any], addr: Any) -> ResponseTypes:
        """
        Request Handler.
        1. Translate JSON -> EngineCommand
        2. Executes via Interface
        3. Formats response for TCP
        """
        try:
            # Convert JSON to EngineCommand
            command = translate_client_message(request, self.user_id_mapper)

            # Execute: Interface handles logic/locking/matching
            # Returns EngineResponse object (success, data, message)
            resp_obj = self.interface.execute(command)

            # Convert EngineRespones object back to a Dictionary for JSON
            response: dict[str, Any] = {
                "status": "ok" if resp_obj.success else "error",
                "message": resp_obj.message,
            }

            # If Interface returned data, merge it in
            if resp_obj.data:
                # If data is a list (eg markets), wrap it
                if isinstance(resp_obj.data, list):
                    # Guessing key based on command, or just put it in "data"
                    # TODO: Let Interface return dicts, or wrap here
                    # Currently assumes get_marketes returns a list
                    if request.get("type") == "get_markets":
                        response["markets"] = resp_obj.data
                    else:
                        response["data"] = resp_obj.data
                elif isinstance(resp_obj.data, dict):
                    response.update(resp_obj.data)

            return response

        except ValueError:
            # If translate_client_message fails,
            # try legacy/info command.
            req_type = request.get("type")

            if req_type == "balance":
                return self._handle_balance(request)
            elif req_type == "proof_of_walk":
                return self._handle_proof_of_walk(request)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown or malformed command: {req_type}",
                }

        except Exception as e:
            print(f"[{addr}] Unexpected Logic Error: {e}")
            if DEBUG_MODE:
                traceback.print_exc()
            return {"status": "error", "message": "Internal server error"}

    # --- Legacy / Info Handlers (Not yet in Interface) ---

    def _handle_proof_of_walk(self, req: dict[str, Any]) -> dict[str, Any]:
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

    def _handle_balance(self, req: dict[str, Any]) -> dict[str, Any]:
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

    # def _handle_read(self, req: dict[str, Any]) -> SnapshotResponse:
    #     """
    #     Return order book snapshot.

    #     TODO: Need market_id in ReadBookRequest.
    #     Currently returns first market as fallback.
    #     """
    #     if not self.engine._markets:
    #         return SnapshotResponse(status="ok", bids=[], asks=[])

    #     # Get first market (will want to specify market_id later)
    #     first_market_id = next(iter(self.engine._markets.keys()))
    #     snap = self.engine.get_market_snapshot(first_market_id)

    #     return SnapshotResponse(status="ok", bids=snap["bids"], asks=snap["asks"])

    # def _handle_get_markets(self) -> dict[str, Any]:
    #     """
    #     Return list of active markets with proper username conversion.

    #     Converts internal ID (1) back to username string ("alice") for client display.
    #     """
    #     raw_markets = self.engine.get_active_markets()
    #     clean_markets = []

    #     for m in raw_markets:
    #         try:
    #             # Parse the market ID to extract internal ID and convert back to username
    #             raw_id = str(m["id"])

    #             # Handle both "," and "_" separators
    #             sep = "," if "," in raw_id else "_"
    #             internal_id_str, minutes = raw_id.split(sep, 1)

    #             # CONVERT BACK: Int(1) -> Str("alice")
    #             real_username = self.user_id_mapper.to_external(int(internal_id_str))

    #             # Rebuild the ID with real username
    #             clean_m = m.copy()
    #             clean_m["id"] = f"{real_username},{minutes}"
    #             clean_markets.append(clean_m)

    #         except Exception:
    #             # Fallback if parsing fails
    #             clean_markets.append(m)

    #     return {"status": "ok", "markets": clean_markets}

    # --- Persistence ---

    def save_world(self) -> None:
        """Save engine, economy, and mapper state to JSON."""
        print("[*] Saving world state...")

        engine_state = self.engine.dump_state()
        economy_state = self.economy.dump_state()
        mapper_state = self.user_id_mapper.dump_state()

        # Engine already returns markets with string keys ("1,480")
        # No conversion needed here
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
            with open(DB_FILE) as f:
                data = json.load(f)

            if "economy" in data:
                self.economy.load_state(data["economy"])

            if "mapper" in data:
                self.user_id_mapper.load_state(data["mapper"])

            if "engine" in data:
                # Engine.load_state handles "1,60" string parsing internally
                self.engine.load_state(data["engine"])

            print(f"[*] Loaded {len(self.economy.accounts)} accounts and {len(self.engine._markets)} markets.")

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

        # We could also use Interface to seed data.
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
