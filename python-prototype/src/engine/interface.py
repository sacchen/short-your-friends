"""
Engine Interface Layer

This module acts as the boundary between the server (JSON/TCP layer) and the
matching engine (pure logic layer). It handles:

1. Type conversions: strings ↔ ints, dollars ↔ cents, UUIDs ↔ stable IDs
2. Coordination: engine + economy operations
3. Command/Response API: clean interface for server to use

Responsibilities:
- Server doesn't know about type conversions
- Engine doesn't know about economy or string types
- Interface bridges the gap
"""

import zlib
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Optional

from orderbook.economy import EconomyManager
from orderbook.id_mapper import UserIdMapper

# --- Command Types ---


class EngineAction(Enum):
    """All possible actions the engine can perform"""

    PLACE_ORDER = auto()
    CANCEL_ORDER = auto()
    SETTLE_MARKETS = auto()
    GET_MARKETS = auto()
    GET_SNAPSHOT = auto()


@dataclass
class EngineCommand:
    """
    Unified command structure for engine operations.
    All fields use ENGINE representation (ints, cents, stable IDs).
    """

    action: EngineAction

    # For PLACE_ORDER
    market_id: Optional[tuple[int, int]] = None
    side: Optional[str] = None
    price: Optional[int] = None  # In cents
    quantity: Optional[int] = None
    order_id: Optional[int] = None
    user_id: Optional[int] = None

    # For CANCEL_ORDER
    # Uses order_id field above

    # For SETTLE_MARKETS
    target_user_id: Optional[int] = None
    actual_screentime_minutes: Optional[int] = None

    # For GET_SNAPSHOT
    # Uses market_id field above


@dataclass
class EngineResponse:
    """
    Unified response structure from engine operations.
    """

    success: bool
    data: Any = None
    message: str = ""


# --- Translation Functions ---


def translate_client_message(
    request: dict[str, Any], user_id_mapper: UserIdMapper
) -> EngineCommand:
    """
    Converts client JSON request into EngineCommand.

    Client representation:
    - user_id: "alice" (string)
    - price: 50 (cents as int)
    - order_id: "uuid-123" (string)
    - market_id: {"target_user_id": "alice", "threshold_minutes": 480}

    Engine representation:
    - user_id: 1 (int)
    - price: 50 (cents as int)
    - order_id: 123456 (stable int)
    - market_id: (1, 480) (tuple of ints)
    """
    req_type = request.get("type")

    if req_type == "place_order":
        # Parse market_id
        # Market ID Format: "alice_480" or "alice,480" -> (internal_id, 480)
        # FIX: Always convert username to internal ID for engine to prevent
        # duplicate markets (e.g., "alice" vs internal ID "1").
        raw_market_id = request["market_id"]
        market_id = _parse_market_id(raw_market_id, user_id_mapper)

        # Convert order ID: accept str or int, convert to int for engine
        # Following same pattern as user_id: flexible in API, int in engine
        order_id = _parse_order_id(request.get("id", 0))

        # Parse user_id
        user_id_str = str(request["user_id"])
        user_id_int = user_id_mapper.to_internal(user_id_str)

        return EngineCommand(
            action=EngineAction.PLACE_ORDER,
            market_id=market_id,
            side=request["side"],
            price=int(request["price"]),  # Already in cents
            quantity=int(request["qty"]),
            order_id=order_id,
            user_id=user_id_int,
        )

    elif req_type == "cancel":
        order_id = _parse_order_id(request["id"])
        return EngineCommand(action=EngineAction.CANCEL_ORDER, order_id=order_id)

    elif req_type == "settle":
        # FIX: Convert string username to internal ID for comparison
        target_user_str = request["target_user_id"]
        target_user_int = user_id_mapper.to_internal(target_user_str)

        return EngineCommand(
            action=EngineAction.SETTLE_MARKETS,
            target_user_id=target_user_int,
            actual_screentime_minutes=int(request["actual_screentime_minutes"]),
        )

    elif req_type == "get_markets":
        return EngineCommand(action=EngineAction.GET_MARKETS)

    elif req_type == "read":
        # TODO: Need market_id in request
        return EngineCommand(action=EngineAction.GET_SNAPSHOT)

    else:
        raise ValueError(f"Unknown request type: {req_type}")


def _parse_market_id(
    raw_market_id: Any, user_id_mapper: UserIdMapper
) -> tuple[int, int]:
    """
    Parses market_id from various client formats into engine format (int, int).

    Supported formats:
    - Dict: {"target_user_id": "alice", "threshold_minutes": 480}
    - String: "alice_480" or "alice,480"

    FIX: Always convert username to internal ID for engine.
    This prevents duplicate markets (eg "alice" vs "1").
    """
    # Clint sent Dict
    if isinstance(raw_market_id, dict):
        target_user = str(raw_market_id["target_user_id"])
        minutes = int(raw_market_id["threshold_minutes"])
    # Client sent String
    elif isinstance(raw_market_id, str):
        if "_" in raw_market_id:
            target_user, minutes_str = raw_market_id.rsplit("_", 1)
        else:
            target_user, minutes_str = raw_market_id.split(",")
        minutes = int(minutes_str)
    else:
        raise ValueError(f"Invalid market_id type: {type(raw_market_id)}")

    # Convert username to internal ID
    target_user_int = user_id_mapper.to_internal(target_user)
    return (target_user_int, minutes)


def _parse_order_id(raw_id: Any) -> int:
    """
    Converts order ID from client format (string/UUID) to engine format (stable int).

    Uses CRC32 for deterministic hashing across restarts.
    Stable conversion so string IDs match the engine's integer IDs.
    """
    if isinstance(raw_id, str):
        # Use CRC32 for a stable, deterministic integer across restarts
        return zlib.crc32(raw_id.encode()) & 0xFFFFFFFF
    return int(raw_id)


# --- Coordination Layer ---


class EngineInterface:
    """
    High-level interface that coordinates engine + economy operations.

    This is the main entry point for server.py to interact with the engine.
    Handles all type conversions and cross-cutting concerns.
    """

    def __init__(
        self,
        engine: Any,  # MatchingEngine
        economy: EconomyManager,
        user_id_mapper: UserIdMapper,
        auditor: Optional[Any] = None,  # SystemAuditor
        debug_mode: bool = True,
    ):
        self.engine = engine
        self.economy = economy
        self.user_id_mapper = user_id_mapper
        self.auditor = auditor
        self.debug_mode = debug_mode

    def execute(self, cmd: EngineCommand) -> EngineResponse:
        """
        Central dispatcher for all engine operations.
        Coordinates engine + economy + auditing.
        """
        try:
            if cmd.action == EngineAction.PLACE_ORDER:
                return self._handle_place_order(cmd)

            elif cmd.action == EngineAction.CANCEL_ORDER:
                return self._handle_cancel_order(cmd)

            elif cmd.action == EngineAction.SETTLE_MARKETS:
                return self._handle_settle(cmd)

            elif cmd.action == EngineAction.GET_MARKETS:
                markets = self._handle_get_markets()
                return EngineResponse(success=True, data=markets)

            elif cmd.action == EngineAction.GET_SNAPSHOT:
                snapshot = self._handle_get_snapshot(cmd)
                return EngineResponse(success=True, data=snapshot)

            else:
                return EngineResponse(
                    success=False, message=f"Unknown action: {cmd.action}"
                )

        except Exception as e:
            return EngineResponse(success=False, message=f"Interface error: {e}")

    def _handle_place_order(self, cmd: EngineCommand) -> EngineResponse:
        """
        Place order with full economy coordination.

        Steps:
        1. Lock funds (if buy order)
        2. Execute matching in engine
        3. Confirm trades in economy
        4. Handle price improvement refunds
        5. Run audit (if debug mode)
        """
        # Convert user_id back to string for economy
        user_id_str = self.user_id_mapper.to_external(cmd.user_id)
        price_decimal = Decimal(cmd.price) / 100  # cents → dollars

        # Step 1: Lock funds for buy orders
        if cmd.side == "buy":
            if not self.economy.attempt_order_lock(
                user_id_str, price_decimal, cmd.quantity
            ):
                return EngineResponse(
                    success=False,
                    message=f"Insufficient funds. Need ${price_decimal * cmd.quantity:.2f}",
                )

        # Step 2: Create market if needed
        if cmd.market_id not in self.engine._markets:
            target_user_str = self.user_id_mapper.to_external(cmd.market_id[0])
            minutes = cmd.market_id[1]
            market_name = f"{target_user_str} Sleep {minutes // 60}:{minutes % 60:02d}"
            self.engine.create_market(cmd.market_id, market_name)

        # Step 3: Execute matching
        try:
            trades = self.engine.process_order(
                market_id=cmd.market_id,
                side=cmd.side,
                price=cmd.price,
                quantity=cmd.quantity,
                order_id=cmd.order_id,
                user_id=cmd.user_id,
            )
        except ValueError as e:
            # Engine rejected (e.g., market closed)
            if cmd.side == "buy":
                self.economy.release_order_lock(
                    user_id_str, price_decimal, cmd.quantity
                )
            return EngineResponse(success=False, message=str(e))

        # Step 4: Confirm trades in economy
        # FIX: Use original username string, not internal ID
        # We need consistent string key for the portfolio dictionary
        target_user_str = self.user_id_mapper.to_external(cmd.market_id[0])
        market_id_str = f"{target_user_str},{cmd.market_id[1]}"

        for trade in trades:
            buyer_str = self.user_id_mapper.to_external(trade.buy_user_id)
            seller_str = self.user_id_mapper.to_external(trade.sell_user_id)
            # Convert cents to dollars (Engine uses cents, Economy uses dollars)
            trade_price_dollars = Decimal(trade.price) / 100

            self.economy.confirm_trade(
                buyer_id=buyer_str,
                seller_id=seller_str,
                market_id=market_id_str,
                price=trade_price_dollars,
                quantity=trade.quantity,
            )

        # Step 5: Price Improvement: Release unused locked funds
        # If buyer got a better price than they locked for, refund the difference
        if cmd.side == "buy" and trades:
            total_paid = sum(Decimal(t.price) / 100 * t.quantity for t in trades)
            total_filled = sum(t.quantity for t in trades)
            total_locked = price_decimal * total_filled
            refund = total_locked - total_paid

            if refund > 0:
                self.economy.release_order_lock(user_id_str, refund, 1)
                if self.debug_mode:
                    print(f"[Interface] Price improvement refund: ${refund:.2f}")

        # Step 6: Audit (if enabled)
        if self.debug_mode and self.auditor:
            try:
                self.auditor.run_full_audit()
            except ValueError as e:
                print(f"CRITICAL: Audit failed after order {cmd.order_id}!")
                return EngineResponse(success=False, message=f"Audit failure: {e}")

        return EngineResponse(
            success=True,
            data={"trades": trades, "num_trades": len(trades)},
            message=f"Order placed. {len(trades)} trades executed.",
        )

    def _handle_cancel_order(self, cmd: EngineCommand) -> EngineResponse:
        """
        Cancel order and release locked funds if buy order.
        Uses O(1) engine lookup.
        """
        meta = self.engine.cancel_order(cmd.order_id)

        if not meta:
            return EngineResponse(
                success=False, message="Order not found or already filled"
            )

        # Release funds if it was a buy order
        # NOTE: We need to know WHO placed the order to refund them.
        if meta.side == "buy":
            user_id_str = self.user_id_mapper.to_external(meta.user_id)
            # Convert cents (Engine) to dollars (Economy)
            price_decimal = Decimal(meta.price) / 100
            self.economy.release_order_lock(user_id_str, price_decimal, meta.quantity)

        return EngineResponse(
            success=True,
            data={"order_id": cmd.order_id},
            message="Order cancelled and funds released",
        )

    def _handle_settle(self, cmd: EngineCommand) -> EngineResponse:
        """
        Settle all markets for target user based on actual screentime.
        """
        all_trades = []
        markets_settled = 0

        # Find and settle all markets for this user
        for market_id in list(self.engine._markets.keys()):
            # Compare internal IDs
            if market_id[0] == cmd.target_user_id:
                threshold = market_id[1]
                # Terminal price: 1 if they met/exceeded threshold, 0 if not
                terminal_price = 1 if cmd.actual_screentime_minutes >= threshold else 0

                trades = self.engine._markets[market_id].settle_market(terminal_price)

                # FIX: Convert internal ID back to username string for economy
                # Confirm trades in economy
                target_user_str = self.user_id_mapper.to_external(market_id[0])
                market_id_str = f"{target_user_str},{market_id[1]}"

                for trade in trades:
                    buyer_str = self.user_id_mapper.to_external(trade.buy_user_id)
                    seller_str = self.user_id_mapper.to_external(trade.sell_user_id)

                    self.economy.confirm_trade(
                        buyer_id=buyer_str,
                        seller_id=seller_str,
                        market_id=market_id_str,
                        price=Decimal(trade.price) / 100,
                        quantity=trade.quantity,
                    )

                all_trades.extend(trades)
                markets_settled += 1

        return EngineResponse(
            success=True,
            data={"markets_settled": markets_settled, "total_trades": len(all_trades)},
            message=f"Settled {markets_settled} markets with {len(all_trades)} trades",
        )

    def _handle_get_markets(self) -> list[dict[str, Any]]:
        """
        Get active markets with username conversion.

        Converts internal ID (1) back to username string ("alice") for client display.
        """
        raw_markets = self.engine.get_active_markets()
        clean_markets = []

        for m in raw_markets:
            try:
                # Parse market ID and convert internal ID back to username
                raw_id = str(m["id"])
                sep = "," if "," in raw_id else "_"
                internal_id_str, minutes = raw_id.split(sep, 1)

                # CONVERT BACK: Int(1) -> Str("alice")
                real_username = self.user_id_mapper.to_external(int(internal_id_str))

                # Rebuild with real username
                clean_m = m.copy()
                clean_m["id"] = f"{real_username},{minutes}"
                clean_markets.append(clean_m)

            except Exception:
                # Fallback if parsing fails
                clean_markets.append(m)

        return clean_markets

    def _handle_get_snapshot(self, cmd: EngineCommand) -> dict[str, Any]:
        """
        Get order book snapshot for a market.
        """
        if not self.engine._markets:
            return {"bids": [], "asks": []}

        # If no market_id specified, use first market
        if cmd.market_id is None:
            market_id = next(iter(self.engine._markets.keys()))
        else:
            market_id = cmd.market_id

        snapshot = self.engine.get_market_snapshot(market_id)
        return snapshot
