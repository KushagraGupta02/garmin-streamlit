"""Headless helper for cron jobs.

  python scripts/garmin_cli.py sync   [--days 30] [--demo]   fetch & cache new data
  python scripts/garmin_cli.py report [--days 90] [--demo]   write reports/YYYY-MM-DD.md
  python scripts/garmin_cli.py status                        cache/token status (no network)

Real data needs a token saved with "Remember me" in the app. The CLI never
asks for or stores a password.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from garmin_app.cache import DiskCache
from garmin_app.config import REPORT_DIR
from garmin_app.config import SAVED_META as META
from garmin_app.config import SAVED_TOKENS as SAVED
from garmin_app.demo import DemoSource
from garmin_app.report import build_report
from garmin_app.sources import GarminSource, load_bundle


def source(demo: bool):
    if demo:
        return DemoSource(), "demo"
    if not META.exists():
        sys.exit("No saved login. Sign in once in the app with 'Remember me', or use --demo.")
    from garminconnect import Garmin

    g = Garmin()
    g.login(str(SAVED))
    key = json.loads(META.read_text())["user_key"]
    return GarminSource(g, DiskCache(key)), key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sync", "report", "status"])
    ap.add_argument("--days", type=int, default=90, help="days of health data")
    ap.add_argument("--years", type=int, default=2, help="years of activities")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.cmd == "status":
        print(f"saved token: {'yes' if META.exists() else 'no'}")
        if META.exists():
            c = DiskCache(json.loads(META.read_text())["user_key"])
            print(f"cache: {c.dir} ({c.file_count()} files, {c.size_bytes() / 1e6:.1f} MB)")
        return

    src, _key = source(a.demo)
    start = dt.date(dt.date.today().year - a.years + 1, 1, 1)
    last = [-1]

    def prog(f: float, m: str) -> None:
        if int(f * 10) != last[0]:
            last[0] = int(f * 10)
            print(f"  {f:4.0%} {m}", file=sys.stderr)

    bundle = load_bundle(src, start, a.days, prog)
    print(f"activities: {len(bundle['activities'])}, health days: {len(bundle['days'])}")
    if a.cmd == "report":
        REPORT_DIR.mkdir(exist_ok=True)
        out = REPORT_DIR / f"{dt.date.today()}{'-demo' if a.demo else ''}.md"
        out.write_text(build_report(bundle, "demo" if a.demo else ""))
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
