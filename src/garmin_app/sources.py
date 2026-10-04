"""Where raw data comes from: the real Garmin Connect account or a demo generator.

Both sources return the same raw JSON shapes Garmin uses, so the rest of the
app (transform, analytics, coach) never knows the difference.
"""

import datetime as dt
import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

from garmin_app.cache import DiskCache
from garmin_app.config import ACTIVITY_TTL, LIVE_DAYS, REQUEST_PAUSE

_LOG = logging.getLogger(__name__)
ProgressFn = Callable[[float, str], None]


class Source(Protocol):
    name: str

    def activities(self, start: dt.date, end: dt.date) -> list[dict]: ...
    def day(self, d: dt.date) -> dict[str, Any]: ...
    def extras(self) -> dict[str, Any]: ...


class GarminSource:
    """Cached, rate-limited wrapper around garminconnect.Garmin.

    A day/year is only written to the cache if every request for it succeeded,
    so a network blip never turns into a permanently empty day.
    """

    name = "garmin"

    def __init__(self, client: Any, cache: DiskCache) -> None:
        self.client = client
        self.cache = cache
        self._failed = False

    def _call(self, fn: Callable[[], Any], default: Any = None) -> Any:
        from garminconnect import (
            GarminConnectAuthenticationError,
            GarminConnectNotFoundError,
            GarminConnectTooManyRequestsError,
        )

        time.sleep(REQUEST_PAUSE)
        try:
            out = fn()
        except GarminConnectNotFoundError:
            return default  # no data for that day: a valid, cacheable answer
        except (GarminConnectAuthenticationError, GarminConnectTooManyRequestsError):
            raise
        except Exception as e:
            _LOG.warning("Garmin call failed, not caching: %s", type(e).__name__)
            self._failed = True
            return default
        return default if out is None else out

    def _cached(self, name: str, fetch: Callable[[], Any], max_age: float | None) -> Any:
        hit = self.cache.get(name, max_age=max_age)
        if hit is not None:
            return hit
        self._failed = False
        value = fetch()
        if not self._failed:
            self.cache.put(name, value)
        return value

    def activities(self, start: dt.date, end: dt.date) -> list[dict]:
        out: list[dict] = []
        today = dt.date.today()
        for year in range(start.year, end.year + 1):
            y0, y1 = max(start, dt.date(year, 1, 1)).isoformat(), min(end, dt.date(year, 12, 31)).isoformat()
            # A finished year is immutable; the current one is refreshed hourly.
            acts = self._cached(
                f"activities-{year}",
                lambda y=year: self._call(lambda: self.client.get_activities_by_date(f"{y}-01-01", f"{y}-12-31"), []),
                max_age=ACTIVITY_TTL if year == today.year else None,
            )
            out += [a for a in acts if y0 <= str(a.get("startTimeLocal", ""))[:10] <= y1]
        return out

    def day(self, d: dt.date) -> dict[str, Any]:
        live = (dt.date.today() - d).days < LIVE_DAYS
        ds = d.isoformat()
        c = self.client

        def fetch() -> dict[str, Any]:
            return {
                "summary": self._call(lambda: c.get_user_summary(ds), {}),
                "sleep": self._call(lambda: c.get_sleep_data(ds), {}),
                "hrv": self._call(lambda: c.get_hrv_data(ds), {}),
                "readiness": self._call(lambda: c.get_training_readiness(ds), []),
            }

        return self._cached(f"day-{ds}", fetch, max_age=900 if live else None)

    def extras(self) -> dict[str, Any]:
        c = self.client
        today = dt.date.today().isoformat()

        def fetch() -> dict[str, Any]:
            return {
                "race_predictions": self._call(c.get_race_predictions, {}),
                "training_status": self._call(lambda: c.get_training_status(today), {}),
                "personal_records": self._call(c.get_personal_record, []),
                "full_name": self._call(c.get_full_name, None),
            }

        return self._cached("extras", fetch, max_age=6 * 3600)


def load_bundle(
    src: Source,
    activity_start: dt.date,
    health_days: int,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """Collect everything the app needs into one raw bundle."""
    today = dt.date.today()
    progress = progress or (lambda _f, _m: None)
    progress(0.02, "Activities")
    acts = src.activities(activity_start, today)
    days: dict[str, Any] = {}
    for i in range(health_days):
        d = today - dt.timedelta(days=health_days - 1 - i)
        days[d.isoformat()] = src.day(d)
        progress(0.05 + 0.9 * (i + 1) / health_days, f"Health data {d}")
    progress(0.97, "Records & predictions")
    extras = src.extras()
    progress(1.0, "Done")
    return {"activities": acts, "days": days, "extras": extras}
