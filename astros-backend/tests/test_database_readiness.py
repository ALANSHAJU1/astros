"""
AstroOS11 — Stage 4: Database Readiness Tests
==============================================

Comprehensive test suite verifying database repository behavior,
deduplication invariants, fallback durations, rejection boundaries,
and operational error handling for AstroOS database services.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import database_recommendations
from app.main import app
from app.models.celestial_event import CelestialEvent
from app.repositories.event_repository import get_events_for_session
from app.services.database_recommendation_service import (
    DEFAULT_DURATIONS,
    get_database_recommendations,
)
from app.services.event_deduplication import deduplicate_events

TZ_IST = ZoneInfo("Asia/Kolkata")
SESSION_START = datetime(2026, 10, 27, 19, 0, tzinfo=TZ_IST)
SESSION_END = datetime(2026, 10, 27, 23, 0, tzinfo=TZ_IST)


# ===========================================================================
# A. Repository Behavior (get_events_for_session)
# ===========================================================================


class TestEventRepositoryQueryBounds:
    """Validate query filtering and boundary edge cases for get_events_for_session."""

    def test_overlapping_events_are_included(self, db):
        """Events that overlap the session in any interval configuration are returned."""
        base_time = SESSION_START

        # 1. Starts before, ends during session
        ev1 = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Test Event Before-During",
            category="planetary",
            event_type="planet",
            start_time=base_time - timedelta(hours=1),
            end_time=base_time + timedelta(hours=1),
            additional_data={},
        )
        # 2. Completely within session
        ev2 = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Test Event Interior",
            category="planetary",
            event_type="planet",
            start_time=base_time + timedelta(hours=1),
            end_time=base_time + timedelta(hours=2),
            additional_data={},
        )
        # 3. Starts during, ends after session
        ev3 = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Test Event During-After",
            category="planetary",
            event_type="planet",
            start_time=SESSION_END - timedelta(hours=1),
            end_time=SESSION_END + timedelta(hours=1),
            additional_data={},
        )
        # 4. Spans entire session
        ev4 = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Test Event Enclosing",
            category="planetary",
            event_type="planet",
            start_time=base_time - timedelta(hours=1),
            end_time=SESSION_END + timedelta(hours=1),
            additional_data={},
        )

        db.add_all([ev1, ev2, ev3, ev4])
        db.flush()

        results = get_events_for_session(
            db=db,
            session_start=SESSION_START,
            session_end=SESSION_END,
            category="planetary",
        )
        result_ids = {e.id for e in results}

        assert ev1.id in result_ids
        assert ev2.id in result_ids
        assert ev3.id in result_ids
        assert ev4.id in result_ids

    def test_event_ending_exactly_at_session_start_is_excluded(self, db):
        """An event whose end_time equals session_start does not overlap and must be excluded."""
        ev = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Boundary Pre-Session",
            category="lunar",
            event_type="moon",
            start_time=SESSION_START - timedelta(hours=2),
            end_time=SESSION_START,  # exact boundary
            additional_data={},
        )
        db.add(ev)
        db.flush()

        results = get_events_for_session(
            db=db,
            session_start=SESSION_START,
            session_end=SESSION_END,
            category="lunar",
        )
        assert ev.id not in {e.id for e in results}

    def test_event_starting_exactly_at_session_end_is_excluded(self, db):
        """An event whose start_time equals session_end does not overlap and must be excluded."""
        ev = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Boundary Post-Session",
            category="lunar",
            event_type="moon",
            start_time=SESSION_END,  # exact boundary
            end_time=SESSION_END + timedelta(hours=2),
            additional_data={},
        )
        db.add(ev)
        db.flush()

        results = get_events_for_session(
            db=db,
            session_start=SESSION_START,
            session_end=SESSION_END,
            category="lunar",
        )
        assert ev.id not in {e.id for e in results}

    def test_instantaneous_event_end_time_none_inside_session(self, db):
        """Events with end_time=None starting inside the session are included."""
        ev = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Instant In Session",
            category="instant_cat",
            event_type="flash",
            start_time=SESSION_START + timedelta(minutes=30),
            end_time=None,
            additional_data={},
        )
        db.add(ev)
        db.flush()

        results = get_events_for_session(
            db=db,
            session_start=SESSION_START,
            session_end=SESSION_END,
            category="instant_cat",
        )
        assert ev.id in {e.id for e in results}

    def test_instantaneous_event_end_time_none_at_boundaries(self, db):
        """Instantaneous events at session_start are included; at session_end are excluded."""
        ev_start = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Instant Exact Start",
            category="boundary_instant",
            event_type="flash",
            start_time=SESSION_START,
            end_time=None,
            additional_data={},
        )
        ev_end = CelestialEvent(
            id=uuid.uuid4(),
            object_name="Instant Exact End",
            category="boundary_instant",
            event_type="flash",
            start_time=SESSION_END,
            end_time=None,
            additional_data={},
        )
        db.add_all([ev_start, ev_end])
        db.flush()

        results = get_events_for_session(
            db=db,
            session_start=SESSION_START,
            session_end=SESSION_END,
            category="boundary_instant",
        )
        result_ids = {e.id for e in results}
        assert ev_start.id in result_ids
        assert ev_end.id not in result_ids

    def test_naive_session_start_rejected(self):
        """Naive start_time raises ValueError before querying database."""
        mock_db = MagicMock()
        naive_start = datetime(2026, 10, 27, 19, 0)
        with pytest.raises(ValueError, match="session_start must be timezone-aware"):
            get_events_for_session(
                db=mock_db,
                session_start=naive_start,
                session_end=SESSION_END,
            )
        mock_db.scalars.assert_not_called()

    def test_naive_session_end_rejected(self):
        """Naive end_time raises ValueError before querying database."""
        mock_db = MagicMock()
        naive_end = datetime(2026, 10, 27, 23, 0)
        with pytest.raises(ValueError, match="session_end must be timezone-aware"):
            get_events_for_session(
                db=mock_db,
                session_start=SESSION_START,
                session_end=naive_end,
            )
        mock_db.scalars.assert_not_called()

    def test_reversed_or_empty_time_range_rejected(self):
        """Reversed or equal time ranges are rejected with a descriptive ValueError."""
        mock_db = MagicMock()
        # Reversed
        with pytest.raises(ValueError, match="session_end must be later than session_start"):
            get_events_for_session(
                db=mock_db,
                session_start=SESSION_END,
                session_end=SESSION_START,
            )
        # Empty
        with pytest.raises(ValueError, match="session_end must be later than session_start"):
            get_events_for_session(
                db=mock_db,
                session_start=SESSION_START,
                session_end=SESSION_START,
            )
        mock_db.scalars.assert_not_called()

    @pytest.mark.parametrize("limit", [1, 100, 500])
    def test_valid_limits_accepted(self, limit):
        """Valid query limits between 1 and 500 are accepted."""
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []
        result = get_events_for_session(
            db=mock_db,
            session_start=SESSION_START,
            session_end=SESSION_END,
            limit=limit,
        )
        assert result == []
        mock_db.scalars.assert_called_once()

    @pytest.mark.parametrize("limit", [0, -1, 501, 1000])
    def test_invalid_limits_rejected(self, limit):
        """Query limits below 1 or above 500 are rejected."""
        mock_db = MagicMock()
        with pytest.raises(ValueError, match="limit must be between 1 and 500"):
            get_events_for_session(
                db=mock_db,
                session_start=SESSION_START,
                session_end=SESSION_END,
                limit=limit,
            )
        mock_db.scalars.assert_not_called()


# ===========================================================================
# B. Event Deduplication Invariants
# ===========================================================================


class TestEventDeduplicationInvariants:
    """Validate deduplicate_events logic and timezone comparisons."""

    def test_duplicate_external_events_retains_latest_end_time(self):
        """When multiple records share an external_event_id, the one with the latest end_time is preserved."""
        start = SESSION_START
        end_shorter = SESSION_START + timedelta(hours=1)
        end_longer = SESSION_START + timedelta(hours=2)

        ev1 = MagicMock(
            external_event_id="nasa-jpl-mars-01",
            category="planet",
            event_type="transit",
            start_time=start,
            end_time=end_shorter,
        )
        ev2 = MagicMock(
            external_event_id="nasa-jpl-mars-01",
            category="planet",
            event_type="transit",
            start_time=start,
            end_time=end_longer,
        )

        # Ordering 1: shorter then longer
        deduped = deduplicate_events([ev1, ev2])
        assert len(deduped) == 1
        assert deduped[0].end_time == end_longer

        # Ordering 2: longer then shorter
        deduped_reverse = deduplicate_events([ev2, ev1])
        assert len(deduped_reverse) == 1
        assert deduped_reverse[0].end_time == end_longer

    def test_distinct_external_events_not_merged(self):
        """Records with different external_event_ids are preserved as distinct events."""
        ev1 = MagicMock(
            external_event_id="ext-01",
            category="planet",
            event_type="transit",
            start_time=SESSION_START,
            end_time=SESSION_END,
        )
        ev2 = MagicMock(
            external_event_id="ext-02",
            category="planet",
            event_type="transit",
            start_time=SESSION_START,
            end_time=SESSION_END,
        )
        deduped = deduplicate_events([ev1, ev2])
        assert len(deduped) == 2

    def test_records_without_external_id_retained_by_id(self):
        """Records with external_event_id=None are keyed by internal id and not merged."""
        ev1 = MagicMock(
            id=uuid.uuid4(),
            external_event_id=None,
            category="deep_sky",
            event_type="nebula",
            start_time=SESSION_START,
            end_time=SESSION_END,
        )
        ev2 = MagicMock(
            id=uuid.uuid4(),
            external_event_id=None,
            category="deep_sky",
            event_type="nebula",
            start_time=SESSION_START,
            end_time=SESSION_END,
        )
        deduped = deduplicate_events([ev1, ev2])
        assert len(deduped) == 2

    def test_cross_timezone_comparisons_execute_without_error(self):
        """Comparing datetimes with different timezone offsets during deduplication does not raise."""
        start_utc = datetime(2026, 10, 27, 13, 30, tzinfo=timezone.utc)
        # Identical moment in Asia/Kolkata
        start_ist = datetime(2026, 10, 27, 19, 0, tzinfo=TZ_IST)

        end_shorter = datetime(2026, 10, 27, 14, 30, tzinfo=timezone.utc)
        end_longer = datetime(2026, 10, 27, 21, 0, tzinfo=TZ_IST)  # 15:30 UTC

        ev_utc = MagicMock(
            external_event_id="tz-test-01",
            category="meteor",
            event_type="shower",
            start_time=start_utc,
            end_time=end_shorter,
        )
        ev_ist = MagicMock(
            external_event_id="tz-test-01",
            category="meteor",
            event_type="shower",
            start_time=start_ist,
            end_time=end_longer,
        )

        deduped = deduplicate_events([ev_utc, ev_ist])
        assert len(deduped) == 1
        assert deduped[0] == ev_ist
        assert deduped[0].end_time == end_longer


# ===========================================================================
# C. Database Recommendation Service
# ===========================================================================


class TestDatabaseRecommendationServiceReadiness:
    """Validate fallback durations, empty result handling, and rejection rules."""

    def test_empty_database_results_handled_gracefully(self):
        """When no events match the session, the service returns empty status and 0 evaluated."""
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []

        session = {
            "location": {"name": "Thrissur", "latitude": 10.5, "longitude": 76.2},
            "start_time": SESSION_START.isoformat(),
            "end_time": SESSION_END.isoformat(),
            "available_duration_minutes": 120,
        }

        result = get_database_recommendations(
            db=mock_db,
            session=session,
            observation_goal="general_observation",
        )

        assert result["status"] == "empty"
        assert result["ranked_events"] == []
        assert result["database_events_found"] == 0
        assert result["database_events_rejected"] == []
        assert result["recommendation"]["summary"]["total_events_evaluated"] == 0

    def test_default_durations_table_coverage(self):
        """Verify standard fallback durations match expected values."""
        assert DEFAULT_DURATIONS["deep_sky"] == 45
        assert DEFAULT_DURATIONS["meteor_shower"] == 30
        assert DEFAULT_DURATIONS["eclipse"] == 20
        assert DEFAULT_DURATIONS["planet"] == 20
        assert DEFAULT_DURATIONS["full_moon"] == 30

    def test_invalid_records_rejected_without_fabricating_scores(self):
        """Events with invalid windows or failing assessments are rejected with reasons."""
        mock_db = MagicMock()

        # 1. End time <= start time
        ev_invalid_window = MagicMock(
            id=uuid.uuid4(),
            external_event_id="bad-window-01",
            object_name="Bad Window Event",
            category="planet",
            event_type="planet",
            start_time=SESSION_START,
            end_time=SESSION_START - timedelta(minutes=10),
            latitude=10.5,
            longitude=76.2,
            additional_data={},
        )
        # 2. Window smaller than required duration (e.g. 5 min window for 20 min event)
        ev_too_short = MagicMock(
            id=uuid.uuid4(),
            external_event_id="too-short-01",
            object_name="Short Window Event",
            category="planet",
            event_type="planet",
            start_time=SESSION_START,
            end_time=SESSION_START + timedelta(minutes=5),
            latitude=10.5,
            longitude=76.2,
            additional_data={},
        )

        mock_db.scalars.return_value.all.return_value = [
            ev_invalid_window,
            ev_too_short,
        ]

        session = {
            "location": {"name": "Thrissur", "latitude": 10.5, "longitude": 76.2},
            "start_time": SESSION_START.isoformat(),
            "end_time": SESSION_END.isoformat(),
            "available_duration_minutes": 120,
        }

        # Assessment provider that would succeed if called
        valid_assessment = {
            "status": "success",
            "visibility_score": 85.0,
            "weather_score": 90.0,
            "source": "unit_test",
        }

        result = get_database_recommendations(
            db=mock_db,
            session=session,
            assessment_provider=lambda e: valid_assessment,
        )

        assert result["database_events_found"] == 2
        rejected = result["database_events_rejected"]
        assert len(rejected) == 2

        reasons = {r["event_id"]: r["reason"] for r in rejected}
        assert reasons[str(ev_invalid_window.id)] == "Event has no valid end time."
        assert reasons[str(ev_too_short.id)] == "Required duration exceeds the event window."
        assert result["status"] == "empty"


# ===========================================================================
# D. Database Failure Handling & Transaction Rollback
# ===========================================================================


class TestDatabaseFailureHandling:
    """Validate behavior when SQLAlchemy encounters operational database errors."""

    def test_operational_error_returns_http_503(self, client, monkeypatch):
        """When an OperationalError is raised, the endpoint returns HTTP 503 Service Unavailable."""
        mock_db = MagicMock()
        mock_db.scalars.side_effect = OperationalError(
            statement="SELECT * FROM celestial_events",
            params={},
            orig=Exception("could not connect to server: Connection refused"),
        )

        # Override dependency
        from app.db.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            payload = {
                "location": {"name": "Thrissur", "latitude": 10.5276, "longitude": 76.2144},
                "start_time": SESSION_START.isoformat(),
                "end_time": SESSION_END.isoformat(),
                "available_duration_minutes": 120,
            }

            response = client.post("/api/v1/recommendations/from-database", json=payload)
            assert response.status_code == 503
            data = response.json()
            assert data["detail"] == "Database service temporarily unavailable"
            # Verify transaction rollback was attempted
            mock_db.rollback.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_internal_exception_details_not_leaked(self, client):
        """The 503 response does not expose SQL statements, passwords, or connection strings."""
        mock_db = MagicMock()
        secret_info = "postgresql://user:SecretPassword123@internal-db:5432/db"
        mock_db.scalars.side_effect = OperationalError(
            statement=f"SELECT secret FROM events WHERE url='{secret_info}'",
            params={},
            orig=Exception("Timeout"),
        )

        from app.db.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            payload = {
                "location": {"name": "Thrissur", "latitude": 10.5, "longitude": 76.2},
                "start_time": SESSION_START.isoformat(),
                "end_time": SESSION_END.isoformat(),
                "available_duration_minutes": 120,
            }
            response = client.post("/api/v1/recommendations/from-database", json=payload)
            assert response.status_code == 503
            response_text = response.text
            assert "SecretPassword123" not in response_text
            assert "SELECT secret" not in response_text
            assert "internal-db" not in response_text
        finally:
            app.dependency_overrides.pop(get_db, None)
