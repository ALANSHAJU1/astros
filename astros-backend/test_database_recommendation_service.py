
from app.db.session import SessionLocal
from app.services.database_recommendation_service import (
    get_database_recommendations,
)


request_session = {
    "location": {
        "name": "Thrissur",
        "latitude": 10.5276,
        "longitude": 76.2144,
        "timezone": "Asia/Kolkata",
    },
    "start_time": "2026-10-27T19:00:00+05:30",
    "end_time": "2026-10-27T21:00:00+05:30",
    "available_duration_minutes": 120,
}

with SessionLocal() as db:
    result = get_database_recommendations(
        db=db,
        session=request_session,
        observation_goal="moon_observation",
        preferences={},
        category="lunar",
    )

print("Database-backed recommendation result:")
print(result)

assert isinstance(result, dict)
assert result.get("data_mode") == "synthetic_test"
assert result.get("database_events_found", 0) >= 0

print("Database recommendation service test passed.")
