from typing import Literal, NotRequired, TypedDict, Union

# Primitives
Side = Literal["buy", "sell"]
CommandType = Literal["limit", "cancel", "read"]


# Request Packets (Client -> Server)
class LimitOrderRequest(TypedDict):
    type: Literal["limit"]  # Discriminator
    side: Side
    price: int
    qty: int
    id: int


class CancelOrderRequest(TypedDict):
    type: Literal["cancel"]
    id: int


class ReadBookRequest(TypedDict):
    type: Literal["read"]


# Sum Type (Tagged Union)
# Any valid message must be one of these three:
ClientMessage = Union[LimitOrderRequest, CancelOrderRequest, ReadBookRequest]


# Response Objects (Server -> Client)
class PriceLevel(TypedDict):
    price: int
    volume: int
    count: int


class SnapshotResponse(TypedDict):
    status: Literal["ok"]
    bids: list[PriceLevel]  # where did Price Level come from?
    asks: list[PriceLevel]


class ActionResponse(TypedDict):
    status: Literal["accepted", "cancelled", "error"]
    message: NotRequired[str]
