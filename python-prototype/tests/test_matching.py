# Usage: uv run pytest

from orderbook.book import OrderBook


def test_full_match_buy_side() -> None:
    """
    Scenario:
    1. Sell Order (Maker) at $100 for 10 qty.
    2. Buy Order (Taker) at $100 for 10 qty.
    Result: 1 Trade, Book Empty.
    """
    book = OrderBook()

    # 1. Maker (Seller)
    trades_1 = book.process_order(side="sell", price=100, quantity=10, order_id=1, user_id=1)
    assert len(trades_1) == 0
    assert book.get_best_ask() == 100

    # 2. Taker (Buyer) matches fully
    trades_2 = book.process_order(side="buy", price=100, quantity=10, order_id=2, user_id=2)

    # Assertions
    assert len(trades_2) == 1
    trade = trades_2[0]

    assert trade.price == 100
    assert trade.quantity == 10
    assert trade.maker_order_id == 1
    assert trade.taker_order_id == 2

    # Book should be empty now
    assert book.get_best_ask() is None
    assert book.get_best_bid() is None


def test_partial_match_price_improvement() -> None:
    """
    Scenario:
    1. Buy Order (Maker) at $100 for 10 qty.
    2. Sell Order (Taker) at $90 (Aggressive) for 5 qty.

    Result:
    - Trade at $100 (Maker's Price! Not $90).
    - Maker still has 5 qty left on book.
    """
    book = OrderBook()

    # 1. Maker (Buyer)
    book.process_order(side="buy", price=100, quantity=10, order_id=1, user_id=1)

    # 2. Taker (Seller) crossing the spread
    trades = book.process_order(side="sell", price=90, quantity=5, order_id=2, user_id=2)

    assert len(trades) == 1
    trade = trades[0]

    # CRITICAL: Trade happened at Maker price ($100), not Taker price ($90)
    assert trade.price == 100
    assert trade.quantity == 5

    # 3. Check Maker's remaining state
    # The Buy order #1 should still be there, but with 5 shares left
    assert book.get_best_bid() == 100
    # (We would need to inspect the node directly to check qty,
    # or trust that get_best_bid returns the right price level)

    # 4. Verify Taker is gone (fully filled)
    assert book.get_best_ask() is None


def test_multi_level_sweep() -> None:
    """
    Scenario: WALKING THE BOOK
    1. Sell Order at $100 (qty 5)
    2. Sell Order at $101 (qty 5)
    3. Buy Order for 8 shares at $102.

    Result:
    - Trade 1: 5 shares @ $100
    - Trade 2: 3 shares @ $101
    """
    book = OrderBook()

    # Setup the sell wall
    book.process_order("sell", 100, 5, 1, user_id=1)
    book.process_order("sell", 101, 5, 2, user_id=2)

    # Taker sweeps through levels
    trades = book.process_order("buy", 102, 8, 3, user_id=3)

    assert len(trades) == 2

    # Trade 1
    assert trades[0].price == 100
    assert trades[0].quantity == 5

    # Trade 2
    assert trades[1].price == 101
    assert trades[1].quantity == 3  # 8 total - 5 filled = 3 remaining

    # Check book state
    assert book.get_best_ask() == 101  # Order #2 still has 2 shares left
