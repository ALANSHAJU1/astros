from datetime import datetime, timezone, timedelta
import pytest

from app.api.routes.observation_plans import (
    _find_best_observation_for_window,
    _parse_ts,
)
from app.models.environmental_observation import EnvironmentalObservation


def test_find_best_observation_timezone_aware_execution():
    """Verify that _find_best_observation_for_window executes without NameError

    and correctly matches observations across mixed timezone representations (+05:30 and UTC).
    """
    win_start = datetime.fromisoformat("2026-10-28T19:30:00+05:30")  # 14:00 UTC
    win_end = datetime.fromisoformat("2026-10-28T21:00:00+05:30")    # 15:30 UTC

    obs_outside = {
        "observed_at": datetime.fromisoformat("2026-10-28T18:00:00+05:30"),  # 12:30 UTC
        "cloud_cover": 90.0,
    }
    obs_matching = {
        "observed_at": datetime.fromisoformat("2026-10-28T20:00:00+05:30"),  # 14:30 UTC (inside)
        "cloud_cover": 10.0,
    }
    obs_next_day = {
        "observed_at": datetime.fromisoformat("2026-10-29T10:00:00+05:30"),
        "cloud_cover": 50.0,
    }

    obs_list = [obs_outside, obs_matching, obs_next_day]

    # Must execute cleanly without NameError: name 'timezone' is not defined
    chosen = _find_best_observation_for_window(win_start, win_end, obs_list)
    assert chosen is not None
    assert chosen["cloud_cover"] == 10.0


def test_find_best_observation_with_orm_models():
    """Verify selection works with EnvironmentalObservation instances."""
    win_start = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)
    win_end = datetime(2026, 10, 28, 15, 30, tzinfo=timezone.utc)

    obs = EnvironmentalObservation(
        observed_at=datetime(2026, 10, 28, 14, 15, tzinfo=timezone.utc),
        cloud_cover=5.0,
    )

    chosen = _find_best_observation_for_window(win_start, win_end, [obs])
    assert chosen is obs

