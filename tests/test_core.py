import datetime as dt

import numpy as np
import pandas as pd
import pytest

from garmin_app import analytics as an
from garmin_app import coach
from garmin_app.cache import DiskCache, user_key
from garmin_app.demo import DemoSource
from garmin_app.report import build_report, frames
from garmin_app.sources import load_bundle
from garmin_app.transform import activities_df, daily_df, trimp


@pytest.fixture(scope="module")
def bundle():
    return load_bundle(DemoSource(seed=1), dt.date.today() - dt.timedelta(days=400), 90)


@pytest.fixture(scope="module")
def fr(bundle):
    return frames(bundle)


def test_transform_shapes(fr):
    acts, daily, rec, ff = fr
    assert len(acts) > 100 and set(acts["sport"]) >= {"Run", "Bike"}
    assert len(daily) == 90
    assert {"hrv_z", "rhr_z", "sleep_h_base"} <= set(rec.columns)
    assert ff.index.is_monotonic_increasing and ff.index[-1] == pd.Timestamp.today().normalize()


def test_transform_handles_missing_fields():
    df = activities_df([{"startTimeLocal": "2025-01-01 07:00:00", "activityType": {"typeKey": "yoga"}, "duration": 1800}])
    assert df.loc[0, "sport"] == "Other" and df.loc[0, "load"] > 0
    assert activities_df([]).empty
    d = daily_df({"2025-01-01": {"summary": {"restingHeartRate": 0}, "sleep": None, "hrv": None, "readiness": []}})
    assert np.isnan(d.loc[0, "rhr"])


def test_trimp_monotonic():
    assert trimp(60, 150, 50, 190) > trimp(60, 120, 50, 190) > 0
    assert np.isnan(trimp(60, np.nan, 50, 190))


def test_fitness_fatigue_constant_load_converges():
    load = pd.Series(50.0, index=pd.date_range("2024-01-01", periods=400))
    ff = an.fitness_fatigue(load)
    assert ff["ctl"].iloc[-1] == pytest.approx(50, rel=0.01)
    assert ff["acwr"].iloc[-1] == pytest.approx(1, rel=0.01)
    assert abs(ff["tsb"].iloc[-1]) < 1


def test_intensity_split():
    acts = pd.DataFrame({"z1": [4.0], "z2": [4.0], "z3": [0.5], "z4": [1.0], "z5": [0.5]})
    s = an.intensity_split(acts)
    assert s["low"] == pytest.approx(80) and s["high"] == pytest.approx(15)
    assert an.classify_distribution(s) == "polarized"


def test_streaks():
    today = pd.Timestamp.today().normalize()
    dates = [today - pd.Timedelta(days=i) for i in (0, 1, 2, 5, 6)]
    s = an.streaks(pd.DataFrame({"date": dates}))
    assert s["current"] == 3 and s["longest"] == 3 and s["rest_gap_max"] == 2


def test_formatting():
    assert an.fmt_pace(4.5) == "4:30/km"
    assert an.fmt_pace(4.999) == "5:00/km"
    assert an.fmt_hms(3725) == "1:02:05"


def test_coach_runs_and_flags_overload(fr):
    acts, _d, rec, ff = fr
    call = coach.today_call(rec, ff, 0)
    assert call.session and call.status in {"good", "warning", "critical", "info"}
    plan = coach.week_plan(call, acts, ff)
    assert len(plan) == 7 and plan["minutes"].ge(0).all()
    # spike the last week -> ACWR rule must fire
    spike = acts.copy()
    recent = spike["date"] > pd.Timestamp.today() - pd.Timedelta(days=7)
    spike.loc[recent, "load"] *= 4
    ff2 = an.fitness_fatigue(an.daily_load(spike))
    rules = {a.rule for a in coach.advise(spike, rec, ff2)}
    assert "ACWR" in rules


def test_recovery_score_bounds():
    good = pd.Series({"hrv_z": 2.0, "rhr_z": -2.0, "sleep_score": 95, "bb_high": 100, "readiness": 95})
    bad = pd.Series({"hrv_z": -3.0, "rhr_z": 3.0, "sleep_score": 30, "bb_high": 15, "readiness": 5})
    assert 0 <= an.recovery_score(bad) < 35 < 70 < an.recovery_score(good) <= 100


def test_report(bundle):
    md = build_report(bundle)
    assert md.startswith("# Garmin report") and "## Next 7 days" in md


def test_cache_roundtrip(tmp_path):
    c = DiskCache("abc", root=tmp_path)
    calls = []
    assert c.get_or_fetch("x", lambda: calls.append(1) or {"a": 1}) == {"a": 1}
    assert c.get_or_fetch("x", lambda: calls.append(1) or {"a": 2}) == {"a": 1}
    assert len(calls) == 1 and c.file_count() == 1
    c.wipe()
    assert not (tmp_path / "abc").exists()


def test_user_key_hides_email():
    k = user_key("Someone@Example.com ")
    assert k == user_key("someone@example.com") and "@" not in k and len(k) == 16
