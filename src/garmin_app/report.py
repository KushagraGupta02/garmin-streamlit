"""Plain-markdown daily report, used by the CLI."""

import datetime as dt
from typing import Any

import numpy as np
import pandas as pd

from garmin_app import analytics as an
from garmin_app import coach
from garmin_app.transform import activities_df, daily_df, estimate_hr_bounds


def frames(bundle: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = daily_df(bundle["days"])
    rest, hmax = estimate_hr_bounds(daily, bundle["activities"])
    acts = activities_df(bundle["activities"], rest, hmax)
    rec = an.recovery_frame(daily) if len(daily) > 1 else daily
    ff = an.fitness_fatigue(an.daily_load(acts))
    return acts, daily, rec, ff


def _f(v: float, fmt: str = "{:.0f}") -> str:
    return "-" if v is None or (isinstance(v, float) and np.isnan(v)) else fmt.format(v)


def build_report(bundle: dict[str, Any], label: str = "") -> str:
    acts, _daily, rec, ff = frames(bundle)
    today = pd.Timestamp.today().normalize()
    call = coach.today_call(rec, ff, an.consecutive_training_days(acts))
    adv = coach.advise(acts, rec, ff)
    plan = coach.week_plan(call, acts, ff)
    last7 = acts[acts["date"] > today - pd.Timedelta(days=7)]
    split = an.intensity_split(acts[acts["date"] > today - pd.Timedelta(days=28)])
    L = [f"# Garmin report {dt.date.today()}" + (f" ({label})" if label else ""), ""]
    L += ["## Today", f"**{call.session}**", *[f"- {r}" for r in call.reasons], ""]
    if len(ff):
        x = ff.iloc[-1]
        L += ["## Load", f"- Fitness (CTL) {_f(x['ctl'])}, fatigue (ATL) {_f(x['atl'])}, form (TSB) {_f(x['tsb'], '{:+.0f}')}, ACWR {_f(x['acwr'], '{:.2f}')}",
              f"- Last 7 days: {len(last7)} sessions, {last7['hours'].sum():.1f} h, {last7['km'].sum():.0f} km",
              f"- 4-week intensity: {_f(split['low'])}% easy / {_f(split['mid'])}% moderate / {_f(split['high'])}% hard ({an.classify_distribution(split)})", ""]
    if len(rec):
        t = rec.tail(7)
        L += ["## Recovery (7-day avg)",
              f"- Sleep {_f(t['sleep_h'].mean(), '{:.1f}')} h, score {_f(t['sleep_score'].mean())}",
              f"- HRV {_f(t['hrv'].mean())} ms, resting HR {_f(t['rhr'].mean())} bpm, stress {_f(t['stress'].mean())}", ""]
    L += ["## Advice"]
    L += [f"- [{a.kind.upper()} / {a.status}] **{a.title}**: {a.why}" for a in adv] or ["- Nothing flagged."]
    L += ["", f"## Next 7 days ({plan.attrs['phase']}, ~{plan.attrs['target_h']:.1f} h)", "", "| day | session | min | how |", "|---|---|---|---|"]
    L += [f"| {r.day} | {r.session} | {r.minutes} | {r.how} |" for r in plan.itertuples()]
    return "\n".join(L) + "\n"
