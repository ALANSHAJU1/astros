
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.event_deduplication import deduplicate_events


@dataclass
class FakeEvent:
    id: str
    external_event_id: str | None
    category: str
    event_type: str
    start_time: datetime
    end_time: datetime | None


def make_event(event_id: str, end_day: int) -> FakeEvent:
    return FakeEvent(
        id=event_id,
        external_event_id="test-moon-001",
        category="lunar",
        event_type="full_moon",
        start_time=datetime(2026, 10, 26, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, end_day, tzinfo=timezone.utc),
    )


def test_duplicate_events_keep_latest_end_time():
    earlier = make_event("event-1", 29)
    later = make_event("event-2", 30)

    result = deduplicate_events([earlier, later])

    assert len(result) == 1
    assert result[0].id == "event-2"


def test_unique_external_ids_are_preserved():
    first = make_event("event-1", 29)
    second = make_event("event-2", 30)
    second.external_event_id = "different-event"

    result = deduplicate_events([first, second])

    assert len(result) == 2


def test_events_without_external_ids_are_not_merged():
    first = make_event("event-1", 29)
    second = make_event("event-2", 30)
    first.external_event_id = None
    second.external_event_id = None

    result = deduplicate_events([first, second])

    assert len(result) == 2


def test_empty_event_list_returns_empty_list():
    assert deduplicate_events([]) == []
