"""Rule-based coach: turns the analytics into "do / avoid / watch" advice.

Each rule is small, explains itself, and cites the number it is based on, so
the advice is auditable. Not medical advice.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from garmin_app import analytics as an


@dataclass
class Advice:
    kind: str  # "do" | "avoid" | "watch"
    status: str  # good | warning | serious | critical | info
    title: str
    why: str
    rule: str = ""


@dataclass
class TodayCall:
    session: str
    status: str
    recovery: float
    reasons: list[str] = field(default_factory=list)


SESSIONS = {
    "rest": ("Rest or mobility only", "critical"),
    "easy": ("Easy aerobic, Z1-Z2, 30-60 min", "warning"),
    "steady": ("Steady endurance, mostly Z2, optional strides", "info"),
    "quality": ("Quality day: intervals or threshold (Z4-Z5)", "good"),
}


def today_call(rec: pd.DataFrame, ff: pd.DataFrame, consecutive: int) -> TodayCall:
    """Pick today's session from recovery and form."""
    last = rec.dropna(subset=["hrv", "rhr", "sleep_h", "readiness", "bb_high"], how="all")
    row = last.iloc[-1] if len(last) else pd.Series(dtype=float)
    score = an.recovery_score(row) if len(row) else np.nan
    tsb = ff["tsb"].iloc[-1] if len(ff) else np.nan
    acwr = ff["acwr"].iloc[-1] if len(ff) else np.nan
    reasons = []
    if not np.isnan(score):
        reasons.append(f"Recovery score {score:.0f}/100 (HRV, resting HR, sleep, Body Battery vs your baseline)")
    if not np.isnan(tsb):
        reasons.append(f"Form (TSB) {tsb:+.0f}")
    if not np.isnan(acwr):
        reasons.append(f"Acute:chronic load ratio {acwr:.2f}")
    if consecutive >= 6:
        reasons.append(f"{consecutive} training days in a row")

    if (not np.isnan(score) and score < 35) or (not np.isnan(tsb) and tsb < -35) or consecutive >= 9:
        key = "rest"
    elif (not np.isnan(score) and score < 55) or (not np.isnan(tsb) and tsb < -20) or (not np.isnan(acwr) and acwr > 1.4) or consecutive >= 6:
        key = "easy"
    elif (np.isnan(score) or score >= 65) and (np.isnan(tsb) or tsb > -15):
        key = "quality"
    else:
        key = "steady"
    title, status = SESSIONS[key]
    return TodayCall(title, status, score, reasons)


def advise(acts: pd.DataFrame, rec: pd.DataFrame, ff: pd.DataFrame) -> list[Advice]:
    out: list[Advice] = []
    today = pd.Timestamp.today().normalize()
    last28 = acts[acts["date"] > today - pd.Timedelta(days=28)]
    last14 = acts[acts["date"] > today - pd.Timedelta(days=14)]

    # 1. load ratio
    if len(ff):
        acwr = ff["acwr"].iloc[-1]
        if acwr > 1.5:
            out.append(Advice("avoid", "critical", "Don't add volume this week",
                              f"Acute:chronic ratio is {acwr:.2f}. Above ~1.5 injury risk rises sharply; hold or cut load until it is back under 1.3.", "ACWR"))
        elif acwr > 1.3:
            out.append(Advice("watch", "warning", "Load is climbing fast",
                              f"Acute:chronic ratio {acwr:.2f}. Fine for a short block, but plan a lighter week soon.", "ACWR"))
        elif acwr < 0.8 and ff["ctl"].iloc[-1] > 10:
            out.append(Advice("do", "good", "You have room to build",
                              f"Acute:chronic ratio {acwr:.2f}: you're training below your recent norm. Add ~10% volume or one extra session.", "ACWR"))

        tsb = ff["tsb"].iloc[-1]
        if tsb < -30:
            out.append(Advice("avoid", "serious", "Skip hard intervals for now",
                              f"Form is {tsb:+.0f}: deep fatigue. Stack easy days until form is above -20.", "TSB"))
        elif tsb > 15 and ff["ctl"].iloc[-1] > 20:
            out.append(Advice("do", "good", "Good moment for a race or a key workout",
                              f"Form is {tsb:+.0f}: you're fresh. If no race is coming, it's also a sign you can train harder.", "TSB"))

        mono = ff["monotony"].iloc[-1]
        if mono > 2.0:
            out.append(Advice("watch", "warning", "Your days are too similar",
                              f"Training monotony is {mono:.1f} (>2 is linked to illness/overtraining). Make easy days easier and hard days harder, add a real rest day.", "Monotony"))

        ctl = ff["ctl"]
        if len(ctl) > 60:
            ch = ctl.iloc[-1] - ctl.iloc[-29]
            if ch < -5:
                out.append(Advice("watch", "warning", "Fitness is slipping",
                                  f"Chronic load (fitness) dropped {abs(ch):.0f} points in 4 weeks. Rebuild gradually: frequency before intensity.", "CTL trend"))
            elif 0 < ch <= 8:
                out.append(Advice("do", "good", "Fitness trend is healthy",
                                  f"Chronic load up {ch:.0f} points in 4 weeks: steady, sustainable progression.", "CTL trend"))
            elif ch > 8:
                out.append(Advice("watch", "warning", "Fitness rising very quickly",
                                  f"Chronic load up {ch:.0f} points in 4 weeks. Gains are good but schedule a recovery week every 3-4 weeks.", "CTL trend"))

    # 2. intensity distribution
    split = an.intensity_split(last28)
    if split["hours"] >= 3:
        if split["mid"] > 25:
            out.append(Advice("avoid", "warning", "Too much 'grey zone' training",
                              f"{split['mid']:.0f}% of the last 4 weeks was in Z3. Moderate efforts tire you without the benefits of truly easy or truly hard work. Slow your easy days down.", "Polarization"))
        if split["low"] < 70:
            out.append(Advice("do", "warning", "More easy volume",
                              f"Only {split['low']:.0f}% of time in Z1-Z2 (target ~80%). Most endurance gains come from easy, aerobic hours.", "80/20"))
        if split["high"] < 5 and split["low"] > 85:
            out.append(Advice("do", "info", "Add one high-intensity session",
                              f"Only {split['high']:.0f}% of time in Z4-Z5. One weekly interval session (e.g. 5x4 min hard) lifts VO2max.", "80/20"))
        if 75 <= split["low"] <= 90 and split["mid"] <= 15:
            out.append(Advice("do", "good", "Intensity balance looks right",
                              f"{split['low']:.0f}% easy / {split['mid']:.0f}% moderate / {split['high']:.0f}% hard over 4 weeks.", "80/20"))

    # 3. run mileage ramp
    rr = an.ramp_rate(acts, "Run")
    if len(rr) >= 5:
        last = rr.iloc[-2]  # last complete week
        if last["avg_prev"] > 5 and last["change_pct"] > 15:
            out.append(Advice("avoid", "serious", "Running distance jumped too fast",
                              f"Last week was {last['km']:.0f} km, {last['change_pct']:.0f}% above your 4-week average. Keep weekly increases near 10%.", "Ramp rate"))

    # 4. missing ingredients
    sports14 = set(last14["sport"])
    main_sport = acts[acts["date"] > today - pd.Timedelta(days=90)]["sport"].mode()
    main_sport = main_sport.iloc[0] if len(main_sport) else None
    if "Strength" not in set(last28["sport"]) and len(last28) >= 4:
        out.append(Advice("do", "info", "Add strength training",
                          "No strength sessions in 4 weeks. Two short sessions a week (squats, lunges, deadlifts, calf raises, core) cut injury risk and improve economy.", "Missing"))
    if main_sport in ("Run", "Bike"):
        sp = last14[last14["sport"] == main_sport]
        long_thr = 1.5 if main_sport == "Run" else 2.5
        if len(sp) >= 3 and sp["hours"].max() < long_thr:
            out.append(Advice("do", "info", f"Schedule a long {main_sport.lower()}",
                              f"Longest {main_sport.lower()} in 2 weeks was {sp['hours'].max() * 60:.0f} min. A weekly long session (> {long_thr * 60:.0f} min easy) builds endurance.", "Long session"))
    if main_sport == "Run" and "Bike" not in sports14 and "Swim" not in sports14 and len(last14) >= 5:
        out.append(Advice("do", "info", "Consider low-impact cross-training",
                          "All recent cardio is running. Swapping one easy run for cycling or swimming keeps the aerobic stimulus with less impact.", "Variety"))

    # 5. rest
    consecutive = an.consecutive_training_days(acts)
    if consecutive >= 7:
        out.append(Advice("avoid", "serious", "Take a rest day",
                          f"{consecutive} training days in a row. Adaptation happens during recovery.", "Rest"))

    # 6. recovery signals
    if len(rec):
        r7 = rec.tail(7)
        sleep7 = r7["sleep_h"].mean()
        if sleep7 < 7:
            out.append(Advice("watch", "serious" if sleep7 < 6.3 else "warning", "Sleep is your limiter",
                              f"Average {sleep7:.1f} h over the last 7 nights. Under 7 h blunts recovery and raises injury risk; aim for 7.5-9 h when training hard.", "Sleep"))
        bt = rec.tail(14)["bedtime"].dropna()
        if len(bt) >= 7 and bt.std() > 1.0:
            out.append(Advice("watch", "info", "Irregular bedtime",
                              f"Bedtime varies by +/-{bt.std() * 60:.0f} min. A consistent bedtime usually improves sleep score more than extra time in bed.", "Sleep"))
        if "hrv_z" in rec:
            hz = rec["hrv_z"].tail(5).mean()
            if hz < -1:
                out.append(Advice("avoid", "serious", "HRV is suppressed",
                                  f"5-day HRV is {abs(hz):.1f} SD below your 4-week baseline: stress, illness, alcohol or fatigue. Keep training easy until it rebounds.", "HRV"))
            elif hz > 0.5:
                out.append(Advice("do", "good", "HRV above baseline",
                                  "Your nervous system is recovering well; a good window for quality work.", "HRV"))
        if "rhr_z" in rec:
            rz = rec["rhr_z"].tail(3).mean()
            rd = (rec["rhr"] - rec["rhr_base"]).tail(3).mean()
            if rz > 1.5 and rd >= 4:
                out.append(Advice("avoid", "critical", "Resting HR is elevated",
                                  f"Resting HR is ~{rd:.0f} bpm above baseline for 3 days, often an early sign of illness. If you feel off, rest.", "RHR"))
        st7 = r7["stress"].mean()
        if st7 > 40:
            out.append(Advice("watch", "warning", "High life stress",
                              f"Average stress {st7:.0f}/100 this week. Total stress counts: reduce training intensity on high-stress days.", "Stress"))
        steps = r7["steps"].mean()
        if steps < 5000:
            out.append(Advice("do", "info", "Move more outside workouts",
                              f"Average {steps:.0f} steps/day. Low daily movement hurts recovery and metabolic health even if you train.", "NEAT"))

    # 7. performance trend, corrected for heat and altitude
    ef = an.efficiency_factor(acts)
    if len(ef) >= 10:
        sea = ef[~ef["altitude"].astype(bool)]
        new = sea[sea["date"] > today - pd.Timedelta(days=42)]
        old = sea[(sea["date"] <= today - pd.Timedelta(days=42)) & (sea["date"] > today - pd.Timedelta(days=126))]
        if len(new) >= 3 and len(old) >= 3:
            ch = 100 * (new["ef"].median() / old["ef"].median() - 1)
            ch_adj = 100 * (new["ef_adj"].median() / old["ef_adj"].median() - 1)
            warmer = new["temp_c"].median() - old["temp_c"].median()
            pct = ef.attrs.get("heat_pct_per_c", 0.0)
            if ch < -3 and ch_adj >= -1.5 and pct > 0 and warmer >= 3:
                out.append(Advice("watch", "info", "Efficiency dip is heat, not fitness",
                                  f"Raw efficiency is down {abs(ch):.1f}%, but runs were {warmer:.0f} C warmer and you lose ~{pct:.1f}% per degree. "
                                  f"Heat-adjusted it's {ch_adj:+.1f}%. Run by heart rate on hot days, not pace, and drink more.", "Heat"))
            elif ch_adj > 2:
                out.append(Advice("do", "good", "Aerobic efficiency is improving",
                                  f"Easy runs are {ch_adj:.1f}% faster per heartbeat (heat-adjusted) than the previous 12 weeks. Whatever you're doing is working.", "Efficiency"))
            elif ch_adj < -3:
                out.append(Advice("watch", "warning", "Aerobic efficiency is dropping",
                                  f"Easy runs are {abs(ch_adj):.1f}% slower per heartbeat even after adjusting for heat (check fatigue, illness or too little easy volume).", "Efficiency"))
        alt = ef[ef["altitude"].astype(bool) & (ef["date"] > today - pd.Timedelta(days=14))]
        if len(alt):
            out.append(Advice("watch", "info", "Altitude sessions in the last 2 weeks",
                              f"{len(alt)} run(s) above {an.ALTITUDE_M:.0f} m (up to {alt['alt_m'].max():.0f} m). Expect slower pace at the same HR for 1-2 weeks; "
                              "they're left out of your efficiency trend.", "Altitude"))

    order = {"critical": 0, "serious": 1, "warning": 2, "good": 3, "info": 4}
    return sorted(out, key=lambda a: order[a.status])


def week_plan(call: TodayCall, acts: pd.DataFrame, ff: pd.DataFrame) -> pd.DataFrame:
    """A 7-day sketch that respects 80/20 and current fatigue."""
    today = pd.Timestamp.today().normalize()
    recent = acts[acts["date"] > today - pd.Timedelta(days=28)]
    weekly_h = recent["hours"].sum() / 4 if len(recent) else 4.0
    main = recent["sport"].mode().iloc[0] if len(recent) else "Run"
    acwr = ff["acwr"].iloc[-1] if len(ff) else 1.0
    if acwr > 1.3 or call.status in ("critical",):
        phase, factor = "Recover", 0.7
    elif acwr < 0.9:
        phase, factor = "Build", 1.1
    else:
        phase, factor = "Maintain", 1.0
    target = weekly_h * factor
    pattern = [
        ("Easy", 0.12, "Z1-Z2"),
        ("Quality", 0.15, "warm-up, 5x4 min Z4-Z5, cool-down"),
        ("Easy + strength", 0.12, "Z2 + 30 min strength"),
        ("Rest", 0.0, "mobility / walk"),
        ("Steady", 0.15, "Z2, last 10 min Z3"),
        ("Long", 0.30, "Z1-Z2, fuel every 45 min"),
        ("Recovery", 0.10, "very easy or cross-train"),
    ]
    if phase == "Recover":
        pattern[1] = ("Easy", 0.12, "Z1-Z2 (no intervals this week)")
    # start the plan with what today's recovery allows
    start_idx = {"rest": 3, "easy": 0, "steady": 4, "quality": 1}
    key = next(k for k, v in SESSIONS.items() if v[0] == call.session)
    i0 = start_idx[key]
    rows = []
    for i in range(7):
        name, share, how = pattern[(i0 + i) % 7]
        d = today + pd.Timedelta(days=i)
        minutes = round(target * share * 60 / 5) * 5
        if main == "Run":
            minutes = min(minutes, 150)  # very long runs cost more than they give
        sport = {"Run": "run", "Bike": "ride", "Swim": "swim"}.get(main, main.lower())
        if name == "Easy + strength":
            label = f"Easy {sport} + strength"
        elif share:
            label = f"{name} {sport}"
        else:
            label = name
        rows.append({"day": d.strftime("%a %d %b"), "session": label, "minutes": minutes, "how": how})
    df = pd.DataFrame(rows)
    df.attrs["phase"] = phase
    df.attrs["target_h"] = target
    return df
