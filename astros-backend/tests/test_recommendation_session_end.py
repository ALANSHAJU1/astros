from datetime import datetime

from app.modules.intelligence.recommendation import backend_interface


IST = "+05:30"
SESSION_START = f"2026-10-26T19:00:00{IST}"
SESSION_END = f"2026-10-26T22:00:00{IST}"


def make_event(name, start, end, duration, score):
    return {
        "name": name,
        "event_type": "Planetary",
        "source": "synthetic-test",
        "visibility_score": score,
        "weather_score": 80,
        "preference_score": 85,
        "window_start": start,
        "window_end": end,
        "duration_minutes": duration,
    }


def test_backend_interface_passes_explicit_session_end(monkeypatch):
    captured = {}

    def fake_pipeline(**kwargs):
        captured.update(kwargs)

        scheduled_events = []
        for event, start_hour in [
            (kwargs["events"][0], 19),
            (kwargs["events"][1], 20),
        ]:
            start = datetime.fromisoformat(
                f"2026-10-26T{start_hour:02d}:00:00{IST}"
            )
            end = start.replace(
                hour=start.hour + 1
            )

            scheduled = dict(event)
            scheduled["scheduled_start"] = start.isoformat()
            scheduled["scheduled_end"] = end.isoformat()
            scheduled["scheduled_duration_minutes"] = 60
            scheduled_events.append(scheduled)

        return {
            "ranked_events": kwargs["events"],
            "summary": {
                "session_start": kwargs["user_start_time"],
                "session_end": kwargs["session_end_time"],
                "user_available_minutes": kwargs[
                    "total_available_duration_minutes"
                ],
                "total_scheduled_minutes": 120,
                "remaining_minutes": 0,
                "total_events_evaluated": 2,
                "total_events_scheduled": 2,
                "total_events_skipped": 0,
            },
            "observation_schedule": scheduled_events,
            "unscheduled_events": [],
        }

    monkeypatch.setattr(
        backend_interface,
        "run_pipeline_recommendations",
        fake_pipeline,
    )

    request = {
        "session": {
            "session_start": SESSION_START,
            "session_end": SESSION_END,
            "available_duration": 120,
            "timezone": "Asia/Kolkata",
            "location": {
                "latitude": 10.0,
                "longitude": 76.0,
                "timezone": "Asia/Kolkata",
            },
            "observation_goal": "planetary",
        },
        "events": [
            make_event(
                "Jupiter",
                SESSION_START,
                SESSION_END,
                60,
                95,
            ),
            make_event(
                "Saturn",
                SESSION_START,
                SESSION_END,
                60,
                90,
            ),
        ],
    }

    response = backend_interface.generate_recommendations(request)

    assert response["status"] == "success"
    assert captured["session_end_time"] == SESSION_END
    assert captured["total_available_duration_minutes"] == 120

    summary = response["recommendation"]["summary"]
    assert summary["session_end"] == SESSION_END
    assert summary["total_scheduled_minutes"] == 120

    for event in response["recommendation"]["schedule"]:
        assert datetime.fromisoformat(
            event["scheduled_end"]
        ) <= datetime.fromisoformat(SESSION_END)
