"""Pure analytics on the tidy frames. No Streamlit, no network: easy to test."""

import numpy as np
import pandas as pd

ZONES = ["z1", "z2", "z3", "z4", "z5"]
RACE_DISTANCES = {"5K": 5.0, "10K": 10.0, "Half": 21.0975, "Marathon": 42.195}


# --- training load --------------------------------------------------------
def daily_load(acts: pd.DataFrame, end: pd.Timestamp | None = None) -> pd.Series:
    """Load per calendar day, zero-filled (rest days count)."""
    if acts.empty:
        return pd.Series(dtype=float)
    s = acts.groupby("date")["load"].sum()
    end = end or pd.Timestamp.today().normalize()
    idx = pd.date_range(s.index.min(), max(end, s.index.max()), freq="D")
    return s.reindex(idx, fill_value=0.0)


def fitness_fatigue(load: pd.Series) -> pd.DataFrame:
    """Banister-style EWMA: CTL (fitness, 42d), ATL (fatigue, 7d), TSB (form).

    TSB uses yesterday's values: form going *into* the day.
    ACWR is the EWMA acute:chronic ratio (Williams et al. 2017).
    Monotony/strain follow Foster (1998) on a rolling 7-day window.
    """
    if load.empty:
        return pd.DataFrame(columns=["load", "ctl", "atl", "tsb", "acwr", "monotony", "strain"])
    ctl = load.ewm(alpha=1 / 42, adjust=False).mean()
    atl = load.ewm(alpha=1 / 7, adjust=False).mean()
    roll = load.rolling(7, min_periods=7)
    sd = roll.std().replace(0, np.nan)
    monotony = (roll.mean() / sd).clip(upper=10)
    return pd.DataFrame(
        {
            "load": load,
            "ctl": ctl,
            "atl": atl,
            "tsb": (ctl - atl).shift(1),
            "acwr": (atl / ctl.replace(0, np.nan)),
            "monotony": monotony,
            "strain": roll.sum() * monotony,
        }
    )


def weekly(acts: pd.DataFrame) -> pd.DataFrame:
    """Per ISO week (Monday) totals per sport."""
    if acts.empty:
        return pd.DataFrame()
    d = acts.assign(week_start=acts["date"] - pd.to_timedelta(acts["date"].dt.weekday, unit="D"))
    return (
        d.groupby(["week_start", "sport"])
        .agg(hours=("hours", "sum"), km=("km", "sum"), load=("load", "sum"), n=("id", "count"))
        .reset_index()
    )


def ramp_rate(acts: pd.DataFrame, sport: str = "Run", weeks: int = 4) -> pd.DataFrame:
    """Week-over-week change in distance for a sport (the 10% rule)."""
    w = weekly(acts)
    if w.empty:
        return w
    w = w[w["sport"] == sport].set_index("week_start")["km"]
    if w.empty:
        return pd.DataFrame()
    idx = pd.date_range(w.index.min(), pd.Timestamp.today().normalize(), freq="W-MON")
    w = w.reindex(idx, fill_value=0.0)
    out = pd.DataFrame({"km": w, "avg_prev": w.shift(1).rolling(weeks, min_periods=1).mean()})
    out["change_pct"] = 100 * (out["km"] / out["avg_prev"].replace(0, np.nan) - 1)
    return out


# --- intensity ------------------------------------------------------------
def zone_hours(acts: pd.DataFrame) -> pd.Series:
    return acts[ZONES].sum().fillna(0)


def intensity_split(acts: pd.DataFrame) -> dict[str, float]:
    """Seiler 3-zone model from 5 Garmin HR zones: low=Z1+Z2, mid=Z3, high=Z4+Z5."""
    z = zone_hours(acts)
    tot = z.sum()
    if tot <= 0:
        return {"low": np.nan, "mid": np.nan, "high": np.nan, "hours": 0.0}
    return {
        "low": 100 * (z["z1"] + z["z2"]) / tot,
        "mid": 100 * z["z3"] / tot,
        "high": 100 * (z["z4"] + z["z5"]) / tot,
        "hours": float(tot),
    }


def classify_distribution(split: dict[str, float]) -> str:
    low, mid, high = split["low"], split["mid"], split["high"]
    if np.isnan(low):
        return "unknown"
    if low >= 75 and high >= mid:
        return "polarized"
    if low >= 75:
        return "pyramidal"
    if mid >= 25:
        return "threshold-heavy"
    if high >= 25:
        return "HIIT-heavy"
    return "mixed"


# --- performance ----------------------------------------------------------
def efficiency_factor(acts: pd.DataFrame, sport: str = "Run") -> pd.DataFrame:
    """Speed (m/min) per heartbeat for steady sessions. Rising = getting fitter."""
    d = acts[(acts["sport"] == sport) & acts["avg_hr"].notna() & (acts["speed_kmh"] > 0)].copy()
    d = d[d["hours"] >= 0.33]
    if d.empty:
        return pd.DataFrame(columns=["date", "ef", "ef_trend"])
    # exclude obviously hard sessions so we compare like with like
    d = d[(d["z4"].fillna(0) + d["z5"].fillna(0)) < 0.35 * d["hours"]]
    d["ef"] = d["speed_kmh"] * 1000 / 60 / d["avg_hr"]
    d = d.set_index("date").sort_index()
    d["ef_trend"] = d["ef"].rolling("42D", min_periods=3).median()
    return d.reset_index()[["date", "ef", "ef_trend", "name", "km", "pace_min_km", "avg_hr"]]


def best_efforts(acts: pd.DataFrame) -> pd.DataFrame:
    """Fastest average pace among runs close to each race distance (+/-8%)."""
    runs = acts[(acts["sport"] == "Run") & acts["km"].notna()]
    rows = []
    for label, km in RACE_DISTANCES.items():
        sel = runs[(runs["km"] >= km * 0.97) & (runs["km"] <= km * 1.08)]
        if sel.empty:
            continue
        b = sel.loc[sel["pace_min_km"].idxmin()]
        rows.append(
            {
                "distance": label,
                "date": b["date"].date(),
                "name": b["name"],
                "km": round(b["km"], 2),
                "pace": fmt_pace(b["pace_min_km"]),
                "est_time": fmt_hms(b["pace_min_km"] * km * 60),
            }
        )
    return pd.DataFrame(rows)


def riegel(time_s: float, d1: float, d2: float, k: float = 1.06) -> float:
    return time_s * (d2 / d1) ** k


def records(acts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sport, g in acts.groupby("sport"):
        for label, col, fn in [
            ("Longest distance", "km", "max"),
            ("Longest duration", "hours", "max"),
            ("Most elevation", "elev_m", "max"),
            ("Highest load", "load", "max"),
        ]:
            v = g[col].dropna()
            if v.empty or v.max() <= 0:
                continue
            r = g.loc[v.idxmax() if fn == "max" else v.idxmin()]
            val = {"km": f"{r[col]:.1f} km", "hours": fmt_hms(r[col] * 3600), "elev_m": f"{r[col]:.0f} m", "load": f"{r[col]:.0f}"}[col]
            rows.append({"sport": sport, "record": label, "value": val, "date": r["date"].date(), "activity": r["name"]})
    return pd.DataFrame(rows)


# --- habits ---------------------------------------------------------------
def streaks(acts: pd.DataFrame) -> dict[str, int]:
    if acts.empty:
        return {"current": 0, "longest": 0, "rest_gap_max": 0}
    days = pd.Series(1, index=pd.DatetimeIndex(acts["date"].unique())).sort_index()
    idx = pd.date_range(days.index.min(), pd.Timestamp.today().normalize(), freq="D")
    active = days.reindex(idx, fill_value=0).astype(bool)
    run_id = (active != active.shift()).cumsum()
    lengths = active.groupby(run_id).agg(["first", "size"])
    on = lengths[lengths["first"]]["size"]
    off = lengths[~lengths["first"]]["size"]
    current = 0
    for v in active[::-1]:
        if not v:
            break
        current += 1
    return {
        "current": current,
        "longest": int(on.max()) if len(on) else 0,
        "rest_gap_max": int(off.max()) if len(off) else 0,
    }


def consecutive_training_days(acts: pd.DataFrame, min_load: float = 30) -> int:
    """Days in a row (ending today or yesterday) with meaningful load."""
    load = daily_load(acts)
    if load.empty:
        return 0
    n = 0
    for v in load[::-1].iloc[(0 if load.iloc[-1] >= min_load else 1):]:
        if v < min_load:
            break
        n += 1
    return n


# --- recovery -------------------------------------------------------------
def recovery_frame(daily: pd.DataFrame) -> pd.DataFrame:
    """Add personal baselines and deviations to daily health data."""
    d = daily.set_index("date").sort_index().copy()
    for col, win in [("hrv", 28), ("rhr", 28), ("sleep_h", 14), ("stress", 28)]:
        if col not in d:
            continue
        base = d[col].rolling(win, min_periods=5).mean().shift(1)
        sd = d[col].rolling(win, min_periods=5).std().shift(1)
        d[f"{col}_base"] = base
        d[f"{col}_z"] = (d[col] - base) / sd.replace(0, np.nan)
    return d.reset_index()


def recovery_score(row: pd.Series) -> float:
    """0-100 composite from HRV, RHR, sleep and Body Battery vs. *your* baseline.

    Uses Garmin's own Training Readiness if present (averaged in), so the score
    still works for watches that don't report readiness.
    """
    parts, weights = [], []

    def add(v: float, w: float) -> None:
        if v is not None and not np.isnan(v):
            parts.append(float(np.clip(v, 0, 100)))
            weights.append(w)

    if "hrv_z" in row:
        add(60 + 15 * row["hrv_z"], 3)
    if "rhr_z" in row:
        add(60 - 15 * row["rhr_z"], 2)
    if "sleep_score" in row:
        add(row["sleep_score"], 2)
    elif "sleep_h" in row:
        add(100 * row["sleep_h"] / 8.5, 2)
    if "bb_high" in row:
        add(row["bb_high"], 1.5)
    if "readiness" in row:
        add(row["readiness"], 3)
    if not parts:
        return np.nan
    return float(np.average(parts, weights=weights))


def lagged_correlations(daily: pd.DataFrame, ff: pd.DataFrame) -> pd.DataFrame:
    """How yesterday's training and last night's sleep relate to today's recovery."""
    d = daily.set_index("date")
    joined = d.join(ff[["load", "tsb"]], how="left")
    joined["load_yday"] = joined["load"].shift(1)
    pairs = [
        ("load_yday", "hrv", "Yesterday's load -> HRV"),
        ("load_yday", "rhr", "Yesterday's load -> resting HR"),
        ("load_yday", "sleep_score", "Yesterday's load -> sleep score"),
        ("sleep_h", "hrv", "Sleep hours -> HRV"),
        ("sleep_h", "readiness", "Sleep hours -> readiness"),
        ("stress", "sleep_score", "Daytime stress -> sleep score"),
        ("bedtime", "sleep_score", "Later bedtime -> sleep score"),
        ("steps", "sleep_score", "Steps -> sleep score"),
        ("tsb", "hrv", "Form (TSB) -> HRV"),
    ]
    rows = []
    for x, y, label in pairs:
        if x not in joined or y not in joined:
            continue
        s = joined[[x, y]].dropna()
        if len(s) < 14:
            continue
        rows.append({"relationship": label, "r": round(spearman(s[x], s[y]), 2), "n": len(s)})
    return pd.DataFrame(rows)


def spearman(x: pd.Series, y: pd.Series) -> float:
    """Rank correlation without needing scipy."""
    return float(x.rank().corr(y.rank()))


# --- formatting -----------------------------------------------------------
def fmt_pace(min_per_km: float) -> str:
    if min_per_km is None or np.isnan(min_per_km):
        return "-"
    m = int(min_per_km)
    s = round((min_per_km - m) * 60)
    if s == 60:
        m, s = m + 1, 0
    return f"{m}:{s:02d}/km"


def fmt_hms(seconds: float) -> str:
    if seconds is None or np.isnan(seconds):
        return "-"
    seconds = round(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
