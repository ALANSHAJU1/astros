from datetime import datetime, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.repositories.event_repository import get_events_for_session


TZ = ZoneInfo("Asia/Kolkata")

SESSION_START = datetime(2026, 10, 27, 19, 0, tzinfo=TZ)
SESSION_END = datetime(2026, 10, 27, 21, 0, tzinfo=TZ)


def make_db_mock(events=None):
    """Create a mocked database session that never connects to PostgreSQL."""
    db = MagicMock()
    db.scalars.return_value.all.return_value = events or []
    return db


def test_returns_events_from_database_query():
    """The repository returns events supplied by the mocked query."""
    expected_events = [
        MagicMock(object_name="Moon", category="lunar"),
        MagicMock(object_name="Mars", category="planet"),
    ]
    db = make_db_mock(expected_events)

    result = get_events_for_session(
        db=db,
        session_start=SESSION_START,
        session_end=SESSION_END,
    )

    assert result == expected_events
    db.scalars.assert_called_once()


def test_empty_query_returns_empty_list():
    """No matching events should produce an empty list."""
    db = make_db_mock()

    result = get_events_for_session(
        db=db,
        session_start=SESSION_START,
        session_end=SESSION_END,
    )

    assert result == []


def test_category_filter_is_applied_to_query():
    """The repository should add a category filter when provided."""
    db = make_db_mock()

    get_events_for_session(
        db=db,
        session_start=SESSION_START,
        session_end=SESSION_END,
        category="lunar",
    )

    db.scalars.assert_called_once()
    statement = db.scalars.call_args.args[0]

    # Confirm the generated SQL statement contains the category condition.
    compiled_sql = str(statement.compile())
    assert "celestial_events.category" in compiled_sql


def test_naive_session_start_is_rejected():
    """The session start must include timezone information."""
    db = make_db_mock()
    naive_start = datetime(2026, 10, 27, 19, 0)

    with pytest.raises(ValueError, match="session_start must be timezone-aware"):
        get_events_for_session(
            db=db,
            session_start=naive_start,
            session_end=SESSION_END,
        )

    db.scalars.assert_not_called()


def test_naive_session_end_is_rejected():
    """The session end must include timezone information."""
    db = make_db_mock()
    naive_end = datetime(2026, 10, 27, 21, 0)

    with pytest.raises(ValueError, match="session_end must be timezone-aware"):
        get_events_for_session(
            db=db,
            session_start=SESSION_START,
            session_end=naive_end,
        )

    db.scalars.assert_not_called()


def test_end_must_be_after_start():
    """An invalid time range must be rejected."""
    db = make_db_mock()

    with pytest.raises(ValueError, match="session_end must be later than session_start"):
        get_events_for_session(
            db=db,
            session_start=SESSION_END,
            session_end=SESSION_START,
        )

    db.scalars.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, 501])
def test_invalid_limit_is_rejected(limit):
    """The limit must be between 1 and 500."""
    db = make_db_mock()

    with pytest.raises(ValueError, match="limit must be between 1 and 500"):
        get_events_for_session(
            db=db,
            session_start=SESSION_START,
            session_end=SESSION_END,
            limit=limit,
        )

    db.scalars.assert_not_called()


def test_utc_timezone_is_accepted():
    """UTC-aware datetimes should also be accepted."""
    db = make_db_mock()

    result = get_events_for_session(
        db=db,
        session_start=datetime(2026, 10, 27, 13, 30, tzinfo=timezone.utc),
        session_end=datetime(2026, 10, 27, 15, 30, tzinfo=timezone.utc),
    )

    assert result == []
    db.scalars.assert_called_once()
