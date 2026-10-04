# Garmin Insights

A self-hosted Streamlit app for your own Garmin Connect data. It combines training statistics,
recovery (sleep, HRV, stress, Body Battery) and a rule-based coach that tells you what to train
and what to skip.

## Run

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py          # http://127.0.0.1:8501
```

Click **Open demo** to try every page with a synthetic athlete, or sign in with your
Garmin account (MFA supported). The first real load downloads about 4 requests per day of
health history, so 90 days takes about 2-3 minutes. After that, past days come from the cache.

## Pages

| Section | Page | What you get |
|---|---|---|
| Today | Dashboard | Today's session call, this week vs last, fitness/fatigue, last night's body metrics, top advice |
| | Coach | Do / avoid / watch cards (each cites the number behind it), 7-day plan (build / maintain / recover) |
| Training | Load & form | CTL/ATL/TSB, acute:chronic ratio, monotony and strain, weekly load by sport, 10% rule, Training Effect |
| | Intensity | Time in zones, 80/20 split and distribution type, weekly zone share, per-sport zones, hard sessions/week |
| | Performance | Race predictions, VO2max, aerobic efficiency (speed per heartbeat), pace at the same HR, cadence, best efforts, power |
| | Statistics | Any measure by week/month/quarter/year and sport, year-over-year cumulative, projection, sport mix |
| Body | Sleep & recovery | Recovery score, HRV vs balanced range, resting HR, sleep stages, bedtime vs score, stress, Body Battery |
| | What affects what | Correlations (e.g. sleep to HRV, load to next-day RHR) plus an explorer for any pair with lag |
| History | Calendar & habits | Yearly heatmaps, streaks, weekday and time-of-day patterns |
| | Records | Longest/biggest per sport, best efforts, Garmin PRs |
| | Activities | Searchable table, CSV/Excel export |
| Account | Privacy & data | Data policy, cache size, logout with optional cache wipe |

## How the coach thinks

Everything lives in `src/garmin_app/coach.py` as small, readable rules:
- load ratio (ACWR 0.8-1.3 sweet spot, >1.5 danger), form (TSB), monotony > 2
- 80/20 intensity, too much Z3, too little high intensity
- running distance ramp > 15% over the prior 4-week average
- missing strength work, missing long session, no low-impact cross-training
- consecutive training days, sleep < 7 h, irregular bedtime, high stress, low steps
- HRV more than 1 SD below baseline, resting HR 4+ bpm above baseline (illness signal)
- aerobic efficiency trend

The rules are heuristics from the sports-science literature. This is not medical advice.

## Data policy (short version)

See `src/garmin_app/privacy.md` (also shown on the login and Privacy pages).

- **Unofficial access.** Garmin has no public API for individuals. This app uses
  [python-garminconnect](https://github.com/cyberjunky/python-garminconnect), which signs in like
  the Garmin Connect mobile app. Garmin's Terms of Use restrict automated access, so keep this to
  personal, low-volume use of your own data. Garmin can change or block the sign-in at any time.
- **Password** is never stored. **Tokens** stay in memory unless you tick *Remember me*, which
  writes them to `data/tokens/` with mode 600. Logout deletes them.
- **Cache** goes to `data/cache/<hash>/`, where the folder name is a hash and not your email. Past days
  are fetched once. Requests are paced (`GARMIN_REQUEST_PAUSE`, default 0.35 s).
- **No telemetry.** Streamlit usage stats are off, there are no analytics or third-party scripts, and the
  server binds to `127.0.0.1`.
- **Don't host it for other people.** You would be collecting their Garmin credentials and
  health data (GDPR special category). For a multi-user app, apply to the official
  [Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/).
- `data/`, `reports/` and exports are git-ignored.

## CLI

```sh
.venv/bin/python scripts/garmin_cli.py status            # token/cache info, no network
.venv/bin/python scripts/garmin_cli.py sync --days 30    # warm the cache (needs Remember me)
.venv/bin/python scripts/garmin_cli.py report            # reports/YYYY-MM-DD.md
.venv/bin/python scripts/garmin_cli.py report --demo     # same with the demo athlete
```

## Development

```sh
.venv/bin/pip install pytest ruff
.venv/bin/ruff check src views scripts tests
.venv/bin/python -m pytest -q      # unit tests and every page rendered in demo mode
```

Layout: `src/garmin_app/` holds the logic (sources, cache, transform, analytics, coach, report)
with no Streamlit in the analytics. `views/` has one file per page and `app.py` handles navigation.
