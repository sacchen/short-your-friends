"""
User ID Mapper: Converts between string (external) and int (internal) user IDs.

API/Economy layers use string IDs
and matching engine uses integer IDs for performance.
"""

from typing import Dict


class UserIdMapper:
    """
    Maps string user IDs to internal integer IDs.

    - API/Economy layers use string IDs
      and matching engine uses integer IDs for performance.
    - Boundary
    """

    def __init__(self) -> None:
        self._str_to_int: Dict[str, int] = {}
        self._int_to_str: Dict[int, str] = {}
        self._next_id: int = 1

    def to_internal(self, user_id: str) -> int:
        """
        Convert string user_id to internal integer ID.

        Creates a new mapping if the user_id hasn't been seen before.

        Input: user_id: str (eg "alice", "test_user_1")

        Returns internal integer ID for matching engine
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

        Input: internal_id: Internal integer ID from matching engine

        Returns original string user_id

        Raises KeyError: If internal_id hasn't been mapped yet
        """
        return self._int_to_str[internal_id]

    def has_external(self, user_id: str) -> bool:
        """Check if a string user_id has been mapped."""
        return user_id in self._str_to_int

    def has_internal(self, internal_id: int) -> bool:
        """Check if an internal ID has been mapped."""
        return internal_id in self._int_to_str
