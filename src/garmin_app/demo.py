"""Synthetic athlete that produces Garmin-shaped JSON.

Used for the "Try demo" button, for tests and for working on the app without
touching anybody's account. Deterministic for a given seed and end date.
"""

import datetime as dt
import math
from typing import Any

import numpy as np

YEARS = 3
EPOCH = dt.datetime(1970, 1, 1)  # Garmin's *Local timestamps are wall-clock ms
# weekday -> (sport typeKey, minutes, intensity 0..1) for a polarized week
WEEK_TEMPLATE = {
    0: None,
    1: ("running", 50, 0.85),  # intervals
    2: ("cycling", 75, 0.35),
    3: ("running", 45, 0.30),
    4: ("strength_training", 40, 0.50),
    5: ("running", 100, 0.40),  # long run
    6: ("cycling", 120, 0.35),
}


class DemoSource:
    name = "demo"

    def __init__(self, seed: int = 7, end: dt.date | None = None) -> None:
        self.end = end or dt.date.today()
        self.start = self.end - dt.timedelta(days=365 * YEARS)
        self.rng = np.random.default_rng(seed)
        self._acts: list[dict] = []
        self._days: dict[str, dict] = {}
        self._build()

    # --- generation -----------------------------------------------------
    def _build(self) -> None:
        rng = self.rng
        n = (self.end - self.start).days + 1
        hr_max, rhr0, vo2 = 188, 52.0, 46.0
        atl = ctl = 0.0
        act_id = 10_000_000_000
        for i in range(n):
            d = self.start + dt.timedelta(days=i)
            week_no = i // 7
            # 3 build weeks then 1 recovery week, slow progression over years
            block = 0.75 if week_no % 4 == 3 else 1.0 + 0.04 * (week_no % 4)
            growth = 0.8 + 0.4 * i / n
            seasonal = 1.0 + 0.15 * math.sin(2 * math.pi * (d.timetuple().tm_yday - 80) / 365)
            plan = WEEK_TEMPLATE[d.weekday()]
            skip = rng.random() < 0.12
            load = 0.0
            if plan and not skip:
                kind, minutes, inten = plan
                if kind == "cycling" and d.month in (12, 1, 2):
                    kind = "indoor_cycling"
                minutes = minutes * block * growth * seasonal * rng.uniform(0.85, 1.15)
                inten = float(np.clip(inten + rng.normal(0, 0.08), 0.15, 0.95))
                act, load = self._activity(act_id, d, kind, minutes, inten, hr_max, rhr0, vo2)
                self._acts.append(act)
                act_id += 1
            if rng.random() < 0.25:  # commute / walk
                act, l2 = self._activity(act_id, d, "walking", rng.uniform(25, 60), 0.1, hr_max, rhr0, vo2)
                self._acts.append(act)
                act_id += 1
                load += l2
            atl += (load - atl) / 7
            ctl += (load - ctl) / 42
            # VO2max drifts toward a level set by fitness (CTL)
            vo2 += 0.01 * (42 + ctl / 12 - vo2) + rng.normal(0, 0.05)
            vo2 = float(np.clip(vo2, 38, 62))
            for a in self._acts[-2:]:
                if a["startTimeLocal"][:10] == d.isoformat() and a["activityType"]["typeKey"].endswith("running"):
                    a["vO2MaxValue"] = round(vo2)
            self._days[d.isoformat()] = self._day(d, atl, ctl, rhr0)

    def _activity(self, aid, d, kind, minutes, inten, hr_max, rhr, vo2):
        rng = self.rng
        dur = minutes * 60
        hr = rhr + (hr_max - rhr) * (0.55 + 0.4 * inten) + rng.normal(0, 3)
        hrr = (hr - rhr) / (hr_max - rhr)
        trimp = minutes * hrr * 0.64 * math.exp(1.92 * hrr)
        speed = {
            "running": 2.4 + 0.035 * (vo2 - 40) + 0.9 * inten,
            "cycling": 6.5 + 0.05 * (vo2 - 40) + 2.0 * inten,
            "indoor_cycling": 0.0,
            "walking": 1.4,
            "strength_training": 0.0,
        }[kind] * rng.uniform(0.95, 1.05)
        # Weather and terrain: wrist sensors read a few degrees above air temperature.
        indoor = kind in ("indoor_cycling", "strength_training")
        air = 20.0 if indoor else 11 + 11 * math.sin(2 * math.pi * (d.timetuple().tm_yday - 110) / 365) + rng.normal(0, 4)
        at_altitude = not indoor and rng.random() < 0.04
        base_elev = rng.uniform(1700, 2400) if at_altitude else rng.uniform(40, 220)
        if kind == "running":
            speed *= 1 - 0.008 * max(0.0, air - 12)  # ~0.8% slower per degree above 12 C
            if at_altitude:
                speed *= 0.95
        dist = speed * dur
        # time in zones: shift weight to higher zones with intensity
        w = np.array([max(0.05, 1 - 2 * inten), 1.2 - inten, 0.3 + inten / 2, 1.2 * inten**2, 0.8 * inten**3])
        if kind in ("walking", "strength_training"):
            w = np.array([0.7, 0.25, 0.05, 0, 0]) + 1e-6
        w = w / w.sum() * dur
        hour = int(rng.choice([6, 7, 12, 17, 18, 19])) if d.weekday() < 5 else int(rng.choice([8, 9, 10]))
        start = dt.datetime.combine(d, dt.time(hour, int(rng.integers(0, 59))))
        names = {
            "running": ["Morning Run", "Intervals", "Easy Run", "Long Run"],
            "cycling": ["Road Ride", "Endurance Ride"],
            "indoor_cycling": ["Indoor Ride"],
            "walking": ["Walk"],
            "strength_training": ["Strength"],
        }[kind]
        act = {
            "activityId": aid,
            "activityName": str(rng.choice(names)),
            "startTimeLocal": start.strftime("%Y-%m-%d %H:%M:%S"),
            "activityType": {"typeKey": kind},
            "distance": round(dist, 1),
            "duration": round(dur, 1),
            "movingDuration": round(dur * 0.97, 1),
            "elevationGain": round(dist / 1000 * rng.uniform(3, 15), 0) if dist else None,
            "averageSpeed": round(speed, 3),
            "maxSpeed": round(speed * 1.4, 3),
            "averageHR": round(hr),
            "maxHR": round(min(hr_max, hr + 15 + 10 * inten)),
            "calories": round(minutes * (6 + 8 * inten)),
            "aerobicTrainingEffect": round(min(5.0, 1.0 + trimp / 40), 1),
            "anaerobicTrainingEffect": round(min(5.0, max(0.0, (inten - 0.5) * 6 + rng.normal(0, 0.3))), 1),
            "activityTrainingLoad": round(trimp * 1.1, 1),
            "averageRunningCadenceInStepsPerMinute": round(166 + 12 * inten + rng.normal(0, 2)) if "running" in kind else None,
            "avgPower": round(150 + 120 * inten) if "cycling" in kind else None,
            "locationName": "Demo Alps" if at_altitude else "Demo City",
            "minTemperature": round(air + 1, 1),
            "maxTemperature": round(air + 7, 1),
            "minElevation": round(base_elev, 1),
            "maxElevation": round(base_elev + (dist / 1000 * rng.uniform(3, 15) if dist else 0), 1),
        }
        for z in range(5):
            act[f"hrTimeInZone_{z + 1}"] = round(float(w[z]), 1)
        return act, trimp

    def _day(self, d, atl, ctl, rhr0):
        rng = self.rng
        fatigue = atl - ctl  # positive = tired
        hrv_base = 62 + 0.05 * ctl
        hrv = hrv_base - 0.35 * fatigue + rng.normal(0, 5)
        rhr = rhr0 - 0.03 * ctl + 0.12 * fatigue + rng.normal(0, 1.5)
        sleep_h = float(np.clip(rng.normal(7.3 if d.weekday() >= 5 else 6.9, 0.7), 4.5, 9.8))
        if rng.random() < 0.08:
            sleep_h -= 1.5
            hrv -= 6
        score = int(np.clip(45 + 7 * (sleep_h - 5.5) + rng.normal(0, 6), 30, 98))
        sec = int(sleep_h * 3600)
        deep, rem = 0.18 + rng.normal(0, 0.03), 0.22 + rng.normal(0, 0.03)
        stress = int(np.clip(30 + 0.4 * fatigue + rng.normal(0, 6) + (5 if d.weekday() < 5 else -5), 12, 70))
        bb_high = int(np.clip(40 + 6 * (sleep_h - 5) - 0.4 * fatigue + rng.normal(0, 6), 15, 100))
        readiness = int(np.clip(50 + 1.2 * (hrv - hrv_base) + 4 * (sleep_h - 7) - 0.8 * fatigue + rng.normal(0, 5), 1, 100))
        steps = int(np.clip(rng.normal(9000, 2500), 2000, 25000))
        return {
            "summary": {
                "calendarDate": d.isoformat(),
                "totalSteps": steps,
                "dailyStepGoal": 9000,
                "restingHeartRate": round(rhr),
                "averageStressLevel": stress,
                "maxStressLevel": min(99, stress + 45),
                "bodyBatteryHighestValue": bb_high,
                "bodyBatteryLowestValue": max(5, bb_high - int(rng.uniform(35, 70))),
                "bodyBatteryChargedValue": int(rng.uniform(30, 70)),
                "bodyBatteryDrainedValue": int(rng.uniform(30, 75)),
                "totalKilocalories": int(2100 + steps * 0.04 + rng.normal(0, 150)),
                "activeKilocalories": int(300 + steps * 0.04),
                "moderateIntensityMinutes": int(rng.uniform(0, 40)),
                "vigorousIntensityMinutes": int(rng.uniform(0, 45)),
                "floorsAscended": int(rng.uniform(2, 20)),
                "averageSpo2": round(float(rng.normal(95.5, 1.0)), 1),
                "avgWakingRespirationValue": round(float(rng.normal(14.5, 0.8)), 1),
            },
            "sleep": {
                "dailySleepDTO": {
                    "calendarDate": d.isoformat(),
                    "sleepTimeSeconds": sec,
                    "deepSleepSeconds": int(sec * deep),
                    "remSleepSeconds": int(sec * rem),
                    "lightSleepSeconds": int(sec * (1 - deep - rem)),
                    "awakeSleepSeconds": int(rng.uniform(600, 2700)),
                    "sleepStartTimestampLocal": int(
                        (dt.datetime.combine(d - dt.timedelta(days=1), dt.time(23, 0)) - EPOCH).total_seconds() * 1000
                        + rng.normal(0, 45 * 60_000)
                    ),
                    "sleepScores": {"overall": {"value": score}},
                },
                "avgOvernightHrv": round(hrv, 1),
            },
            "hrv": {
                "hrvSummary": {
                    "lastNightAvg": round(hrv),
                    "weeklyAvg": round(hrv + rng.normal(0, 2)),
                    "status": "BALANCED" if hrv > hrv_base - 8 else "UNBALANCED",
                    "baseline": {"balancedLow": round(hrv_base - 7), "balancedUpper": round(hrv_base + 8)},
                }
            },
            "readiness": [{"score": readiness, "level": _level(readiness)}],
        }

    # --- Source protocol -------------------------------------------------
    def activities(self, start: dt.date, end: dt.date) -> list[dict]:
        a, b = start.isoformat(), end.isoformat()
        return [x for x in self._acts if a <= x["startTimeLocal"][:10] <= b]

    def day(self, d: dt.date) -> dict[str, Any]:
        return self._days.get(d.isoformat(), {})

    def extras(self) -> dict[str, Any]:
        return {
            "race_predictions": {"time5K": 1335, "time10K": 2790, "timeHalfMarathon": 6240, "timeMarathon": 13290},
            "training_status": {},
            "personal_records": [],
            "full_name": "Demo Athlete",
        }


def _level(score: int) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 50:
        return "MODERATE"
    if score >= 25:
        return "LOW"
    return "POOR"
