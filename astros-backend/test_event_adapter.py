
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.repositories.event_repository import get_events_for_session
from app.services.event_adapter import adapt_celestial_event

tz = ZoneInfo("Asia/Kolkata")

session_start = datetime(2026, 10, 27, 19, 0, tzinfo=tz)
session_end = datetime(2026, 10, 27, 21, 0, tzinfo=tz)

with SessionLocal() as db:
    events = get_events_for_session(
        db=db,
        session_start=session_start,
        session_end=session_end,
        category="lunar",
    )

    print(f"Database events found: {len(events)}")

    for event in events:
        adapted, errors = adapt_celestial_event(event)

        print(f"\nEvent: {event.object_name} ({event.id})")

        if errors:
            print("Not ready for recommendations:")
            for error in errors:
                print(f" - {error}")
        else:
            print("Adapter output:")
            print(adapted)
