
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.celestial_event import CelestialEvent

with SessionLocal() as db:
    statement = (
        select(CelestialEvent)
        .where(CelestialEvent.external_event_id == "test-moon-001")
        .order_by(CelestialEvent.start_time)
    )

    events = db.scalars(statement).all()

    print(f"Matching records: {len(events)}")

    for event in events:
        print({
            "id": str(event.id),
            "external_event_id": event.external_event_id,
            "category": event.category,
            "object_name": event.object_name,
            "event_type": event.event_type,
            "start_time": event.start_time.isoformat(),
            "end_time": (
                event.end_time.isoformat()
                if event.end_time else None
            ),
        })
