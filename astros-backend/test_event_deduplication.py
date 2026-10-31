
from app.db.session import SessionLocal
from app.repositories.event_repository import get_events_for_session
from app.services.event_deduplication import deduplicate_events
from datetime import datetime
from zoneinfo import ZoneInfo

tz = ZoneInfo("Asia/Kolkata")
start = datetime(2026, 10, 27, 19, 0, tzinfo=tz)
end = datetime(2026, 10, 27, 21, 0, tzinfo=tz)

with SessionLocal() as db:
    events = get_events_for_session(
        db, start, end, category="lunar"
    )

    deduplicated = deduplicate_events(events)

    print("Before:", len(events))
    print("After:", len(deduplicated))

    for event in deduplicated:
        print(
            event.external_event_id,
            event.start_time.isoformat(),
            event.end_time.isoformat() if event.end_time else None,
        )

    assert len(deduplicated) == 1

print("Event deduplication test passed.")
