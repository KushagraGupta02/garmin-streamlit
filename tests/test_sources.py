import datetime as dt

import pytest
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError, GarminConnectTooManyRequestsError

from garmin_app import sources
from garmin_app.cache import DiskCache
from garmin_app.sources import GarminSource


class FakeClient:
    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.calls = 0

    def _maybe_fail(self):
        self.calls += 1
        if self.fail_with:
            raise self.fail_with("boom")

    def get_user_summary(self, d):
        self._maybe_fail()
        return {"totalSteps": 1000}

    def get_sleep_data(self, d):
        return {}

    def get_hrv_data(self, d):
        return None

    def get_training_readiness(self, d):
        return []


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(sources, "REQUEST_PAUSE", 0)


def test_clean_day_is_cached(tmp_path):
    c = FakeClient()
    src = GarminSource(c, DiskCache("u", root=tmp_path))
    d = dt.date(2024, 5, 1)
    assert src.day(d)["summary"]["totalSteps"] == 1000
    src.day(d)
    assert c.calls == 1  # second read came from disk


def test_failed_day_is_not_cached(tmp_path):
    c = FakeClient(fail_with=GarminConnectConnectionError)
    src = GarminSource(c, DiskCache("u", root=tmp_path))
    d = dt.date(2024, 5, 1)
    assert src.day(d)["summary"] == {}
    src.day(d)
    assert c.calls == 2  # retried, not served from a poisoned cache


def test_not_found_is_cached_as_empty(tmp_path):
    c = FakeClient(fail_with=GarminConnectNotFoundError)
    src = GarminSource(c, DiskCache("u", root=tmp_path))
    src.day(dt.date(2024, 5, 1))
    src.day(dt.date(2024, 5, 1))
    assert c.calls == 1


def test_rate_limit_propagates(tmp_path):
    src = GarminSource(FakeClient(fail_with=GarminConnectTooManyRequestsError), DiskCache("u", root=tmp_path))
    with pytest.raises(GarminConnectTooManyRequestsError):
        src.day(dt.date(2024, 5, 1))
