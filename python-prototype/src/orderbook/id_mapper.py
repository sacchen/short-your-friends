"""
User ID Mapper: Converts between string (external) and int (internal) user IDs.

API/Economy layers use string IDs
and matching engine uses integer IDs for performance.
"""

from typing import Any


class UserIdMapper:
    """
    Maps string user IDs to internal integer IDs.
    """

    def __init__(self) -> None:
        self._str_to_int: dict[str, int] = {}
        self._int_to_str: dict[int, str] = {}
        self._next_id: int = 1

    def to_internal(self, user_id: str) -> int:
        """
        Convert string user_id to internal integer ID.
        Creates a new mapping if the user_id hasn't been seen before.
        """
        if user_id not in self._str_to_int:
            internal_id = self._next_id
            self._next_id += 1
            self._str_to_int[user_id] = internal_id
            self._int_to_str[internal_id] = user_id
        return self._str_to_int[user_id]

    def to_external(self, internal_id: int) -> str:
        """
        Convert internal integer ID back to string user_id.
        """
        if internal_id not in self._int_to_str:
            raise KeyError(f"Unknown internal ID: {internal_id}")
        return self._int_to_str[internal_id]

    def has_external(self, user_id: str) -> bool:
        """Check if a string user_id has been mapped."""
        return user_id in self._str_to_int

    def has_internal(self, internal_id: int) -> bool:
        """Check if an internal ID has been mapped."""
        return internal_id in self._int_to_str

    # Persistence Methods for server.py

    def dump_state(self) -> dict[str, Any]:
        """Return state dict for JSON saving."""
        return {"map": self._str_to_int, "next_id": self._next_id}

    def load_state(self, state: dict[str, Any]) -> None:
        """Restore state from JSON dict."""
        self._str_to_int = state.get("map", {})
        self._next_id = state.get("next_id", 1)

        # Rebuild the reverse map (internal -> external)
        # JSON loads keys as strings, but values remain ints (which is what we want)
        self._int_to_str = {}
        for k, v in self._str_to_int.items():
            self._int_to_str[v] = k
