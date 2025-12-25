# Usage: uv run pytest

from orderbook.book import OrderBook


def test_bid_priority():
    book = OrderBook()
    # Add bids at different prices
    book.add_order("buy", 100, 10, 1, user_id=1)
    book.add_order("buy", 105, 10, 2, user_id=2)
    book.add_order("buy", 95, 10, 3, user_id=3)

    # Best bid should be 105 (Highest)
    assert book.get_best_bid() == 105


def test_ask_priority():
    book = OrderBook()
    # Add asks at different prices
    book.add_order("sell", 100, 10, 1, user_id=1)
    book.add_order("sell", 105, 10, 2, user_id=2)
    book.add_order("sell", 95, 10, 3, user_id=3)

    # Best ask should be 95 (Lowest)
    assert book.get_best_ask() == 95


def test_lazy_deletion_bids():
    book = OrderBook()
    book.add_order("buy", 100, 10, 1, user_id=1)  # Best price
    book.add_order("buy", 99, 10, 2, user_id=2)  # Second best

    assert book.get_best_bid() == 100

    # Cancel the best bid
    book.cancel_order(1)

    # The heap still has 100 internally, but get_best_bid should skip it
    # and return 99
    assert book.get_best_bid() == 99


def test_lazy_deletion_asks():
    book = OrderBook()
    book.add_order("sell", 100, 10, 1, user_id=1)  # Best price
    book.add_order("sell", 101, 10, 2, user_id=2)  # Second best

    assert book.get_best_ask() == 100

    # Cancel the best ask
    book.cancel_order(1)

    assert book.get_best_ask() == 101


def test_time_priority_fifo():
    """
    Scenario:
    1. Alice sells 10 @ $100 (Order ID 1)
    2. Bob sells 10 @ $100 (Order ID 2) -- Same price, but later time
    3. Charlie buys 10 @ $100.

    Result:
    - Alice gets filled. Bob gets nothing.
    """
    book = OrderBook()

    # 1. Alice (Early Bird)
    book.process_order("sell", 100, 10, 1, user_id=1)

    # 2. Bob (Late Arrival)
    book.process_order("sell", 100, 10, 2, user_id=2)

    # 3. Charlie (Taker)
    trades = book.process_order("buy", 100, 10, 3, user_id=3)

    assert len(trades) == 1
    trade = trades[0]

    # CRITICAL: The maker_order_id MUST be 1 (Alice), not 2 (Bob)
    assert trade.maker_order_id == 1

    # Check book: Bob should still be there
    # (Assuming your book exposes a way to peek at the queue)
    # assert book.asks[100].head.order_id == 2
