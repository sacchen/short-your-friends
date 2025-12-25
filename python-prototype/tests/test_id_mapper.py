# tests/test_id_mapper.py
# Usage: uv run pytest
# or
# uv run pytest tests/test_id_mapper.py -v

from orderbook.id_mapper import UserIdMapper


def test_basic_conversion():
    """Test basic string to int conversion."""
    mapper = UserIdMapper()

    # Convert string to internal ID
    internal_id = mapper.to_internal("alice")
    assert isinstance(internal_id, int)
    assert internal_id == 1  # First ID should be 1


def test_idempotent_mapping():
    """Same string should always map to same int."""
    mapper = UserIdMapper()

    id1 = mapper.to_internal("alice")
    id2 = mapper.to_internal("alice")
    id3 = mapper.to_internal("alice")

    assert id1 == id2 == id3
    assert id1 == 1


def test_sequential_id_assignment():
    """IDs should be assigned sequentially starting from 1."""
    mapper = UserIdMapper()

    alice_id = mapper.to_internal("alice")
    bob_id = mapper.to_internal("bob")
    charlie_id = mapper.to_internal("charlie")

    assert alice_id == 1
    assert bob_id == 2
    assert charlie_id == 3


def test_bidirectional_mapping():
    """Test converting back from internal ID to string."""
    mapper = UserIdMapper()

    # Forward
    internal_id = mapper.to_internal("alice")
    assert internal_id == 1

    # Backward
    external_id = mapper.to_external(internal_id)
    assert external_id == "alice"


def test_multiple_users():
    """Test mapping multiple different users."""
    mapper = UserIdMapper()

    users = ["alice", "bob", "charlie", "dave"]
    internal_ids = []

    for user in users:
        internal_id = mapper.to_internal(user)
        internal_ids.append(internal_id)

    # Should all be unique
    assert len(set(internal_ids)) == len(internal_ids)

    # Should be sequential
    assert internal_ids == [1, 2, 3, 4]

    # Should convert back correctly
    for user, internal_id in zip(users, internal_ids):
        assert mapper.to_external(internal_id) == user


def test_has_external():
    """Test has_external method."""
    mapper = UserIdMapper()

    assert not mapper.has_external("alice")

    mapper.to_internal("alice")
    assert mapper.has_external("alice")
    assert not mapper.has_external("bob")


def test_has_internal():
    """Test has_internal method."""
    mapper = UserIdMapper()

    assert not mapper.has_internal(1)

    internal_id = mapper.to_internal("alice")
    assert mapper.has_internal(internal_id)
    assert not mapper.has_internal(999)


def test_to_external_raises_keyerror():
    """Test that to_external raises KeyError for unmapped IDs."""
    mapper = UserIdMapper()

    # Don't map anything, try to convert
    try:
        mapper.to_external(1)
        assert False, "Should have raised KeyError"
    except KeyError:
        pass  # Expected


def test_round_trip_multiple():
    """Test round-trip conversion for multiple users."""
    mapper = UserIdMapper()

    test_users = ["user_1", "user_2", "test_alice", "bob123"]

    # Convert all to internal
    internal_ids = [mapper.to_internal(user) for user in test_users]

    # Convert all back to external
    round_trip_users = [mapper.to_external(id) for id in internal_ids]

    # Should match original
    assert round_trip_users == test_users


def test_different_string_formats():
    """Test that mapper handles different string formats."""
    mapper = UserIdMapper()

    # UUID-like
    uuid_id = mapper.to_internal("550e8400-e29b-41d4-a716-446655440000")
    assert uuid_id == 1

    # Numeric string
    numeric_id = mapper.to_internal("12345")
    assert numeric_id == 2

    # Email-like
    email_id = mapper.to_internal("user@example.com")
    assert email_id == 3

    # Verify round-trip
    assert mapper.to_external(uuid_id) == "550e8400-e29b-41d4-a716-446655440000"
    assert mapper.to_external(numeric_id) == "12345"
    assert mapper.to_external(email_id) == "user@example.com"
