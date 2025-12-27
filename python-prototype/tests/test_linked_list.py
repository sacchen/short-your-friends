# tests/test_linked_list.py
# Usage: uv run pytest

import time

from orderbook.linked_list import OrderList
from orderbook.node import OrderNode


def create_order(id: int, qty: int) -> OrderNode:
    return OrderNode(
        order_id=id, user_id=0, price=100, quantity=qty, timestamp=time.time()
    )


def test_append_updates_volume():
    ol = OrderList()
    o1 = create_order(1, 10)
    o2 = create_order(2, 5)

    ol.append(o1)
    assert ol.head == o1
    assert ol.tail == o1
    assert ol.total_volume == 10

    ol.append(o2)
    assert ol.head == o1
    assert ol.tail == o2
    assert ol.total_volume == 15
    assert o1.next_node == o2
    assert o2.prev_node == o1


def test_remove_head():
    ol = OrderList()
    o1 = create_order(1, 10)
    o2 = create_order(2, 20)
    ol.append(o1)
    ol.append(o2)

    ol.remove(o1)

    assert ol.head == o2
    assert ol.count == 1
    assert ol.total_volume == 20
    assert o2.prev_node is None


def test_remove_tail():
    ol = OrderList()
    o1 = create_order(1, 10)
    o2 = create_order(2, 20)
    ol.append(o1)
    ol.append(o2)

    ol.remove(o2)

    assert ol.tail == o1
    assert ol.count == 1
    assert ol.total_volume == 10
    assert o1.next_node is None


def test_remove_middle():
    ol = OrderList()
    o1 = create_order(1, 10)
    o2 = create_order(2, 20)
    o3 = create_order(3, 30)
    ol.append(o1)
    ol.append(o2)
    ol.append(o3)

    ol.remove(o2)

    assert ol.count == 2
    assert ol.total_volume == 40
    assert o1.next_node == o3
    assert o3.prev_node == o1
