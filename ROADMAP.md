# Roadmap

## Next up
- [ ] Taper planner: pick a race date, show the projected CTL/TSB curve and a 2-week taper that lands TSB at +10 to +20
- [ ] Sleep-debt meter: rolling 14-day deficit vs a personal sleep need (median sleep on high-readiness days)
- [ ] Illness early warning: combine RHR +5, HRV -1 SD, respiration up and skin temp (if present) into one alert
- [ ] Per-sport HR zones: separate run vs bike zone distribution (bike HR typically lower)
- [ ] Cycling power curve and eFTP trend from activity `maxAvgPower_*` fields (needs-data)
- [ ] Running dynamics: ground contact time, vertical ratio vs pace (needs-data)
- [ ] Weekly goal tracker: user-set hours/km targets with progress bars, stored in session only
- [ ] Gear mileage: shoe km via `get_gear` / `get_gear_stats`, warn at 600-800 km (needs-data)
- [ ] Monthly PDF/markdown digest from `garmin_cli.py report --period month`
- [ ] Strength training volume from exercise sets (`get_activity_exercise_sets`) (needs-data)
- [ ] Women's health: cycle-phase overlay on HRV/RHR when menstrual data is present (opt-in, needs-data)

## Done
- [x] Heat & altitude adjustment: flag efficiency drops on hot days (activity `minTemperature`/`maxTemperature`) so the coach doesn't blame fitness
- [x] Login with MFA, remember-me tokens, demo mode, logout + cache wipe
- [x] Dashboard, coach (do/avoid/watch + 7-day plan), load & form (CTL/ATL/TSB, ACWR, monotony, strain, 10% rule)
- [x] Intensity (zones, 80/20, distribution type), performance (VO2max, efficiency factor, pace@HR, cadence, best efforts, race predictions)
- [x] Statistics (week/month/quarter/year, year-over-year cumulative), sleep & recovery, correlations explorer
- [x] Calendar heatmaps, streaks, time-of-day patterns, records, activity table + CSV/Excel export
