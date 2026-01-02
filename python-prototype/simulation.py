# Usage: PYTHONPATH=src uv run simulation.py

import asyncio
import json
import random
import sys
from typing import Any, NoReturn, TypedDict, cast

# NoReturn for infinite loops: functions never exits

HOST = "127.0.0.1"
PORT = 8888


# Define a Type for MARKET ID
class MarketIdDict(TypedDict):
    target_user_id: int
    threshold_minutes: int


# Specific market we're trading on.
MARKET_ID: MarketIdDict = {"target_user_id": 1, "threshold_minutes": 60}


# Network Helpers
async def send_json(writer: asyncio.StreamWriter, data: dict[str, Any]) -> None:
    """
    Helper to send NDJSON.
    Encodes the string to bytes before writing to socket.
    """
    message = json.dumps(data) + "\n"
    writer.write(message.encode())
    # Drain pauses executions until OS clears buffer.
    # Prevents overwhelming socket if we send too fast.
    await writer.drain()


async def read_json(reader: asyncio.StreamReader) -> dict[str, Any]:
    """
    Helper to read one line of JSON response.
    Blocks until a newline (\n) is received.
    """
    data = await reader.readuntil(b"\n")
    return cast(dict[str, Any], json.loads(data.decode()))


# Market Maker
class MarketMakerBot:
    """
    The House (Liquidity Provider).
    Bets on mean reversion.
    Profits from the difference between Buy and Sell price.
    """

    def __init__(self, name: str, start_price: int, volatility: int):
        self.name = name
        self.fair_price = start_price
        self.volatility = volatility

    async def run(self) -> NoReturn:
        # Establish connection to Engine
        try:
            reader, writer = await asyncio.open_connection(HOST, PORT)
            print(f"[+] [{self.name}] Connected as Market Maker")
        except ConnectionRefusedError:
            print(f"[!] [{self.name}] Could not connect. Is server.py running?")
            sys.exit(1)

        try:
            while True:
                # Random Walk: Simulate external factors.
                # IRL: Order flow imbalance.
                change = random.choice([-1, 0, 0, 0, 1])
                self.fair_price += change

                self.fair_price = max(10, min(90, self.fair_price))

                # Calculate Spread.
                # Widen Spread when volatility is high.
                bid_price = self.fair_price - self.volatility
                ask_price = self.fair_price + self.volatility

                # Place Orders (Quoting)
                # Two-Sided Quote: Simultaneous Buy and Sell

                # Side : BID (Buy Limit)
                await send_json(
                    writer,
                    {
                        "type": "limit",
                        "market_id": MARKET_ID,
                        "side": "buy",
                        "price": bid_price,
                        "qty": 5,
                        "user_id": 101,
                        "id": random.randint(1000, 999999),
                    },
                )
                _ = await read_json(reader)  # Consume confirmation

                # Side : ASK (Sell Limit)
                await send_json(
                    writer,
                    {
                        "type": "limit",
                        "market_id": MARKET_ID,
                        "side": "sell",
                        "price": ask_price,
                        "qty": 5,
                        "user_id": 101,
                        "id": random.randint(1000, 999999),
                    },
                )
                _ = await read_json(reader)  # Consume confirmation

                # Wait.
                # It's discrete events.
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[!] [{self.name}] Crash: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


# Gambler
class LiquidityTakerBot:
    """
    Takers remove liquidity from the book.
    They pay the spread to enter a position immediately.
    """

    def __init__(self, name: str):
        self.name = name

    async def run(self) -> NoReturn:
        try:
            reader, writer = await asyncio.open_connection(HOST, PORT)
            print(f"[+] [{self.name}] Connected as Gambler")
        except ConnectionRefusedError:
            sys.exit(1)

        try:
            while True:
                # Wait
                await asyncio.sleep(random.uniform(1.0, 3.0))

                side = random.choice(["buy", "sell"])

                # Aggressive Pricing:
                # If Buying, pay $100 (Max) for fill.
                # If Selling, ask $0 (Min) for dump.
                price = 100 if side == "buy" else 0
                qty = random.randint(1, 3)

                # Send the order
                await send_json(
                    writer,
                    {
                        "type": "limit",
                        "market_id": MARKET_ID,
                        "side": side,
                        "price": price,
                        "qty": qty,
                        "user_id": 777,
                        "id": random.randint(1000, 999999),
                    },
                )

                # Don't print for clean console
                _ = await read_json(reader)

        except Exception as e:
            print(f"[!] [{self.name}] Crash: {e}")
            sys.exit(1)


# Ticker
async def ticker_tape() -> NoReturn:
    """
    Bloomberg Terminal.
    Asks server for book state and renders it.
    """
    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
    except ConnectionRefusedError:
        print("[!] Ticker could not connect.")
        sys.exit(1)

    try:
        while True:
            # Fetch State
            # Later: Modify "read" in server.py to accept market_id
            # Right now: server returns the first market it finds.
            await send_json(writer, {"type": "read"})
            resp = await read_json(reader)

            bids = resp.get("bids", [])
            asks = resp.get("asks", [])

            # Sort
            # Bids: Highest price is best (Top)
            bids.sort(key=lambda x: x["price"], reverse=True)
            # Asks: Lowest price is best (Top)
            asks.sort(key=lambda x: x["price"])

            # Clear Screen
            print("\033[H\033[J", end="")

            # Render Header
            print("=== SHORTYOURFRIENDS LOB ===")
            print(f"Market: User {MARKET_ID['target_user_id']} > {MARKET_ID['threshold_minutes']}m")
            print(f"Spread: {calculate_spread(bids, asks)}")
            print("-" * 42)
            print(f"{'BID QTY':<10} | {'PRICE':^12} | {'ASK QTY':>10}")
            print("-" * 42)

            # Render Header
            print("=== SHORTYOURFRIENDS LOB ===")
            print(f"Market: User {MARKET_ID['target_user_id']} > {MARKET_ID['threshold_minutes']}m")
            print(f"Spread: {calculate_spread(bids, asks)}")
            print("-" * 42)
            print(f"{'BID QTY':<10} | {'PRICE':^12} | {'ASK QTY':>10}")
            print("-" * 42)

            # Render Rows (Top 10 Levels)
            # Standard LOB view shows bids on left (green), asks on right (red)
            # Format: BID_QTY | BID_PRICE    ASK_PRICE | ASK_QTY
            for i in range(10):
                if i < len(bids) and i < len(asks):
                    # Both bid and ask exist at this level
                    print(
                        f"\033[92m{bids[i]['volume']:<10}\033[0m | "
                        f"\033[92m{bids[i]['price']:>4}\033[0m  "
                        f"\033[93m{asks[i]['price']:<4}\033[0m | "
                        f"\033[91m{asks[i]['volume']:>10}\033[0m"
                    )
                elif i < len(bids):
                    # Only bid exists
                    print(f"\033[92m{bids[i]['volume']:<10}\033[0m | \033[92m{bids[i]['price']:^12}\033[0m | {'':>10}")
                elif i < len(asks):
                    # Only ask exists
                    print(f"{'':<10} | \033[91m{asks[i]['price']:^12}\033[0m | \033[91m{asks[i]['volume']:>10}\033[0m")
                else:
                    # Empty row
                    print(f"{'':<10} | {'':^12} | {'':>10}")

            print("-" * 42)
            await asyncio.sleep(0.2)

    except Exception:
        # If server dies, exit
        sys.exit(0)


def calculate_spread(bids: list[dict[str, Any]], asks: list[dict[str, Any]]) -> str:
    if not bids or not asks:
        return "Inf"
    best_bid = bids[0]["price"]
    best_ask = asks[0]["price"]
    return f"${best_ask - best_bid}"


# Entry Point


async def main() -> None:
    print("[*] Starting Market Simulation...")
    print("[*] Ensure server.py is running in another terminal!")
    await asyncio.sleep(1)

    # Initialize Bots
    maker = MarketMakerBot(name="Jane", start_price=50, volatility=2)
    gambler = LiquidityTakerBot(name="RoaringKitty")

    # Run everything concurrently
    # gather() runs these functions in parallel on the same event loop
    await asyncio.gather(ticker_tape(), maker.run(), gambler.run())


if __name__ == "__main__":
    try:
        # Windows support for asyncio
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Simulation Stopped.")
