
# tests/test_event_repository_integration.py

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models.celestial_event import CelestialEvent
from app.repositories.event_repository import get_events_for_session


TZ = ZoneInfo("Asia/Kolkata")

SESSION_START = datetime(2026, 10, 27, 19, 0, tzinfo=TZ)
SESSION_END = datetime(2026, 10, 27, 21, 0, tzinfo=TZ)


def add_event(
    db,
    *,
    category="lunar",
    start_time=SESSION_START,
    end_time=SESSION_END,
    event_type="full_moon",
    object_name="Test Moon",
):
    event = CelestialEvent(
        external_event_id=f"integration-{uuid4()}",
        category=category,
        object_name=object_name,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        latitude=10.5276,
        longitude=76.2144,
        additional_data={"test_fixture": True},
    )
    db.add(event)
    db.flush()
    return event


def test_overlapping_event_is_returned(db):
    event = add_event(
        db,
        start_time=datetime(2026, 10, 27, 18, 0, tzinfo=TZ),
        end_time=datetime(2026, 10, 27, 20, 0, tzinfo=TZ),
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    assert event.id in {item.id for item in results}


def test_event_ending_before_session_is_excluded(db):
    add_event(
        db,
        start_time=datetime(2026, 10, 27, 17, 0, tzinfo=TZ),
        end_time=datetime(2026, 10, 27, 18, 0, tzinfo=TZ),
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    assert results == []


def test_event_starting_after_session_is_excluded(db):
    add_event(
        db,
        start_time=datetime(2026, 10, 27, 21, 0, tzinfo=TZ),
        end_time=datetime(2026, 10, 27, 22, 0, tzinfo=TZ),
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    assert results == []


def test_category_filter_returns_only_matching_category(db):
    lunar_event = add_event(db, category="lunar")
    add_event(db, category="planet", object_name="Test Mars")

    results = get_events_for_session(
        db, SESSION_START, SESSION_END, category="lunar"
    )

    assert {event.id for event in results} == {lunar_event.id}


def test_null_end_time_inside_session_is_returned(db):
    event = add_event(
        db,
        start_time=datetime(2026, 10, 27, 20, 0, tzinfo=TZ),
        end_time=None,
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    assert event.id in {item.id for item in results}


def test_null_end_time_at_session_end_is_excluded(db):
    add_event(
        db,
        start_time=SESSION_END,
        end_time=None,
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    assert results == []


def test_event_ending_exactly_at_session_start_is_excluded(db):
    add_event(
        db,
        start_time=datetime(2026, 10, 27, 18, 0, tzinfo=TZ),
        end_time=SESSION_START,
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    assert results == []


def test_event_starting_exactly_at_session_start_is_returned(db):
    event = add_event(
        db,
        start_time=SESSION_START,
        end_time=datetime(2026, 10, 27, 20, 0, tzinfo=TZ),
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    assert event.id in {item.id for item in results}


def test_results_are_ordered_by_start_time(db):
    later_event = add_event(
        db,
        start_time=datetime(2026, 10, 27, 20, 0, tzinfo=TZ),
        end_time=datetime(2026, 10, 27, 20, 30, tzinfo=TZ),
        object_name="Later Event",
    )
    earlier_event = add_event(
        db,
        start_time=datetime(2026, 10, 27, 19, 0, tzinfo=TZ),
        end_time=datetime(2026, 10, 27, 19, 30, tzinfo=TZ),
        object_name="Earlier Event",
    )

    results = get_events_for_session(
        db, SESSION_START, SESSION_END
    )

    result_ids = [event.id for event in results]
    assert result_ids.index(earlier_event.id) < result_ids.index(later_event.id)


@pytest.mark.parametrize("limit", [0, -1, 501])
def test_invalid_limit_is_rejected_before_query(db, limit):
    with pytest.raises(ValueError, match="limit must be between 1 and 500"):
        get_events_for_session(
            db,
            SESSION_START,
            SESSION_END,
            limit=limit,
        )
