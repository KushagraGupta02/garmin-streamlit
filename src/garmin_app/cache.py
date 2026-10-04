"""Tiny on-disk JSON cache, one directory per user.

Finished days never change, so they are cached forever. Live data (today,
current-year activity list) is re-fetched once it is older than its TTL.
Everything lives under data/cache/<user_key>/ and can be wiped from the
Privacy page.
"""

import hashlib
import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from garmin_app.config import CACHE_DIR


def user_key(identity: str) -> str:
    """Stable, non-reversible folder name for a user (no email on disk)."""
    return hashlib.sha256(identity.strip().lower().encode()).hexdigest()[:16]


class DiskCache:
    def __init__(self, key: str, root: Path = CACHE_DIR) -> None:
        self.dir = root / key
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        return self.dir / f"{safe}.json"

    def get(self, name: str, max_age: float | None = None) -> Any | None:
        p = self._path(name)
        if not p.exists():
            return None
        if max_age is not None and time.time() - p.stat().st_mtime > max_age:
            return None
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None

    def put(self, name: str, value: Any) -> None:
        p = self._path(name)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value))
        tmp.replace(p)

    def get_or_fetch(
        self, name: str, fetch: Callable[[], Any], max_age: float | None = None
    ) -> Any:
        hit = self.get(name, max_age=max_age)
        if hit is not None:
            return hit
        value = fetch()
        self.put(name, value)
        return value

    def size_bytes(self) -> int:
        return sum(f.stat().st_size for f in self.dir.glob("*.json"))

    def file_count(self) -> int:
        return sum(1 for _ in self.dir.glob("*.json"))

    def wipe(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)
