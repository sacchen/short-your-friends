# Order book design decisions
*Dec 16, 2025*

## Overview: The Core Problem
We are building a limit order book. An order book keeps tracks of Buy and Sell orders and matches the highest Bidder to the lowest Seller. In our shortyourfriends game, we use the order book to keep track of bets and resolve who gets them right.


## Architecture: Dictionary + Linked List

### Two-Level Dictionary Structure
We use two dictionary structures:
- `_orders: Dict[order_id, OrderNode]` for fast cancellation
- `_bids/_asks: Dict[price, OrderList]` for grouping by price

At the first level, `_bids/_asks: Dict[price, OrderList]` groups all buy/sell orders at the same price together. This gives us O(1) lookup to find all orders at $50.

At the second level, each `OrderList` is a doubly linked list of orders at that specific price.

We also maintain a global dictionary `_orders: Dict[order_id, OrderNode]` that maps order_id directly to the node, giving us O(1) cancellation.
  
### Time Priority and FIFO Ordering
Within each price level's OrderList, we use a doubly linked list ordered by time. Each OrderList is a linked list of orders at that price. The head holds the oldest older and the tail holds the newest. This implements time priority where if two orders have the same price, the one that arrived first gets matched first.

## Implementation Details

### Doubly Linked Lists

### Price Priority with Min-Heaps
To match orders, we want to always know which Buy order is the highest and which Sell order is the lowest. Typically, min-heaps sort with the lowest value first. By adding negative values in front of our Buy orders, big Buy numbers are more negative and available in the min-heap.

A min-heap gives you the smallest value first. For asks (sell orders), we want the lowest price. Min-heap gives us this.

For bids (buy orders), we want the highest price. Since min-heap gives us the lowest, we store negative prices. So higher prices are more negative and the min-heap gives us the highest bid.

### Lazy Deletion Strategy
When an order is canceled, we remove it from the Linked List and the `_orders` dict, but we don't remove it from the Heap.

If that cancellation makes a price level empty, we remove the price from the `_bids` dict, but leave the price in the heap until it floats to the top.

Later, when we want the best bid, we look at the heap for a price and then check if the price is still in the `_bids` dict.

Otherwise, if we removed it from the heap immediately, then it would be O(n) to look through the heap. Checking the dictionary is O(1), and then we only check if it's a valid price when we need to use the heap.

## Order Matching

### The Matching Algorithm


### Partial Fill Handling
Buyers and sellers usually want a different quantity of things. What happens if a Seller doesn't sell enough for you to buy? You buy what they have and buy the rest from another Seller. This satisfies more trades.


### Price Discovery: Maker vs Taker

## Settlement

### Market Closure Before Settlement
