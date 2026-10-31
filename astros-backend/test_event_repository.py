
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.repositories.event_repository import get_events_for_session


tz = ZoneInfo("Asia/Kolkata")

start = datetime(2026, 10, 27, 19, 0, tzinfo=tz)
end = datetime(2026, 10, 27, 21, 0, tzinfo=tz)

with SessionLocal() as db:
    events = get_events_for_session(
        db=db,
        session_start=start,
        session_end=end,
        category="lunar",
    )

    print(f"Events found: {len(events)}")

    for event in events:
        print({
            "id": str(event.id),
            "name": event.object_name,
            "category": event.category,
            "event_type": event.event_type,
            "start_time": event.start_time.isoformat(),
            "end_time": (
                event.end_time.isoformat()
                if event.end_time
                else None
            ),
            "additional_data": event.additional_data,
        })
