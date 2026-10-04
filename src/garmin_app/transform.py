"""Raw Garmin JSON -> tidy pandas DataFrames."""

import math
from typing import Any

import numpy as np
import pandas as pd

from garmin_app.config import TYPE_TO_GROUP

ACTIVITY_COLUMNS = [
    "id", "date", "start", "name", "type", "sport", "year", "month", "week",
    "weekday", "hour", "km", "hours", "moving_hours", "elev_m", "speed_kmh",
    "pace_min_km", "avg_hr", "max_hr", "calories", "te_aerobic", "te_anaerobic",
    "load", "vo2max", "cadence", "avg_power", "z1", "z2", "z3", "z4", "z5",
    "location", "temp_c", "alt_m",
]  # fmt: skip


def _num(v: Any) -> float:
    try:
        return float(v) if v is not None else np.nan
    except (TypeError, ValueError):
        return np.nan


def _dig(d: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def trimp(minutes: float, avg_hr: float, hr_rest: float, hr_max: float) -> float:
    """Banister TRIMP; used when Garmin gives no training load."""
    if any(math.isnan(x) for x in (minutes, avg_hr)) or hr_max <= hr_rest:
        return np.nan
    hrr = min(max((avg_hr - hr_rest) / (hr_max - hr_rest), 0.0), 1.0)
    return minutes * hrr * 0.64 * math.exp(1.92 * hrr)


def activities_df(raw: list[dict], hr_rest: float = 55, hr_max: float = 190) -> pd.DataFrame:
    rows = []
    for a in raw:
        start = pd.to_datetime(a.get("startTimeLocal"), errors="coerce")
        if pd.isna(start):
            continue
        type_key = _dig(a, "activityType", "typeKey") or "other"
        dist = _num(a.get("distance"))
        dur = _num(a.get("duration"))
        speed = _num(a.get("averageSpeed"))
        km = dist / 1000 if dist == dist else np.nan
        rows.append(
            {
                "id": a.get("activityId"),
                "start": start,
                "name": a.get("activityName") or "",
                "type": type_key,
                "sport": TYPE_TO_GROUP.get(type_key, "Other"),
                "km": km if km and km > 0 else np.nan,
                "hours": dur / 3600,
                "moving_hours": _num(a.get("movingDuration")) / 3600,
                "elev_m": _num(a.get("elevationGain")),
                "speed_kmh": speed * 3.6 if speed and speed > 0 else np.nan,
                "avg_hr": _num(a.get("averageHR")),
                "max_hr": _num(a.get("maxHR")),
                "calories": _num(a.get("calories")),
                "te_aerobic": _num(a.get("aerobicTrainingEffect")),
                "te_anaerobic": _num(a.get("anaerobicTrainingEffect")),
                "load": _num(a.get("activityTrainingLoad")),
                "vo2max": _num(a.get("vO2MaxValue")),
                "cadence": _num(a.get("averageRunningCadenceInStepsPerMinute")),
                "avg_power": _num(a.get("avgPower")),
                **{f"z{i}": _num(a.get(f"hrTimeInZone_{i}")) / 3600 for i in range(1, 6)},
                "location": a.get("locationName") or "",
                # device-sensor temperature (reads warm on the wrist) and highest point
                "temp_c": np.nanmean([_num(a.get("minTemperature")), _num(a.get("maxTemperature"))])
                if a.get("minTemperature") is not None or a.get("maxTemperature") is not None
                else np.nan,
                "alt_m": _num(a.get("maxElevation")),
            }
        )
    if not rows:
        return pd.DataFrame(columns=ACTIVITY_COLUMNS)
    df = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)
    df["date"] = df["start"].dt.normalize()
    df["year"] = df["start"].dt.year
    df["month"] = df["start"].dt.month
    df["week"] = df["start"].dt.isocalendar().week.astype(int)
    df["weekday"] = df["start"].dt.day_name()
    df["hour"] = df["start"].dt.hour
    df["pace_min_km"] = np.where(df["speed_kmh"] > 0, 60 / df["speed_kmh"], np.nan)
    # Fill missing training load with TRIMP so every session counts.
    missing = df["load"].isna()
    df.loc[missing, "load"] = [
        trimp(h * 60, hr, hr_rest, hr_max)
        for h, hr in zip(df.loc[missing, "hours"], df.loc[missing, "avg_hr"], strict=True)
    ]
    # last resort: 1 point per minute at low intensity
    df["load"] = df["load"].fillna(df["hours"] * 60 * 0.5)
    return df[ACTIVITY_COLUMNS]


def daily_df(days: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for date, d in days.items():
        s = d.get("summary") or {}
        sl = d.get("sleep") or {}
        dto = sl.get("dailySleepDTO") or {}
        hrv = _dig(d.get("hrv"), "hrvSummary") or {}
        ready = d.get("readiness") or []
        ready0 = ready[0] if isinstance(ready, list) and ready else (ready if isinstance(ready, dict) else {})
        sleep_s = _num(dto.get("sleepTimeSeconds"))
        start_ms = dto.get("sleepStartTimestampLocal")
        bed = np.nan
        if start_ms:
            t = pd.to_datetime(start_ms, unit="ms")
            # hours relative to midnight, e.g. 23:30 -> -0.5, 00:30 -> 0.5
            bed = t.hour + t.minute / 60
            bed = bed - 24 if bed > 12 else bed
        rows.append(
            {
                "date": pd.Timestamp(date),
                "steps": _num(s.get("totalSteps")),
                "step_goal": _num(s.get("dailyStepGoal")),
                "rhr": _num(s.get("restingHeartRate")),
                "stress": _num(s.get("averageStressLevel")),
                "bb_high": _num(s.get("bodyBatteryHighestValue")),
                "bb_low": _num(s.get("bodyBatteryLowestValue")),
                "bb_charged": _num(s.get("bodyBatteryChargedValue")),
                "bb_drained": _num(s.get("bodyBatteryDrainedValue")),
                "kcal": _num(s.get("totalKilocalories")),
                "active_kcal": _num(s.get("activeKilocalories")),
                "intensity_min": _num(s.get("moderateIntensityMinutes"))
                + 2 * _num(s.get("vigorousIntensityMinutes")),
                "floors": _num(s.get("floorsAscended")),
                "spo2": _num(s.get("averageSpo2")),
                "respiration": _num(s.get("avgWakingRespirationValue")),
                "sleep_h": sleep_s / 3600,
                "deep_h": _num(dto.get("deepSleepSeconds")) / 3600,
                "rem_h": _num(dto.get("remSleepSeconds")) / 3600,
                "light_h": _num(dto.get("lightSleepSeconds")) / 3600,
                "awake_h": _num(dto.get("awakeSleepSeconds")) / 3600,
                "sleep_score": _num(_dig(dto, "sleepScores", "overall", "value")),
                "bedtime": bed,
                "hrv": _num(hrv.get("lastNightAvg") or sl.get("avgOvernightHrv")),
                "hrv_weekly": _num(hrv.get("weeklyAvg")),
                "hrv_low": _num(_dig(hrv, "baseline", "balancedLow")),
                "hrv_high": _num(_dig(hrv, "baseline", "balancedUpper")),
                "hrv_status": hrv.get("status") or "",
                "readiness": _num(ready0.get("score")),
                "readiness_level": ready0.get("level") or "",
            }
        )
    if not rows:
        return pd.DataFrame(columns=["date"])
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    # Garmin reports 0 for "no data" on several fields.
    for c in ["steps", "rhr", "stress", "bb_high", "sleep_h", "hrv", "spo2"]:
        df.loc[df[c] <= 0, c] = np.nan
    return df


def estimate_hr_bounds(daily: pd.DataFrame, acts_raw: list[dict]) -> tuple[float, float]:
    """Resting HR from daily data, max HR from the 98th pct of activity max HR."""
    rest = float(daily["rhr"].median()) if "rhr" in daily and daily["rhr"].notna().any() else 55.0
    maxes = [float(a["maxHR"]) for a in acts_raw if a.get("maxHR")]
    hmax = float(np.percentile(maxes, 98)) if len(maxes) >= 5 else 190.0
    return rest, max(hmax, rest + 60)
