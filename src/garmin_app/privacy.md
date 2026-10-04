**What this app is.** A self-hosted dashboard for *your own* Garmin Connect data. It talks to Garmin through the open-source, unofficial [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect) library, which signs in the same way the Garmin Connect mobile app does. Garmin does not offer a public API for individuals; the official [Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/) is for approved businesses.

**Your password** goes straight to Garmin's sign-in service and is never saved, logged or cached.

**Tokens.** After sign-in Garmin issues OAuth tokens. They live in memory for this browser session only. If you tick *Remember me*, they are written to `data/tokens/` on the machine running the app (file mode 600). *Logout* deletes them. Tokens are not revoked at Garmin by logout; you can end all sessions from Garmin Connect account settings.

**Your data** (activities, sleep, HRV, stress, Body Battery, readiness) is fetched on demand and cached as JSON under `data/cache/<random id>/` so finished days are never downloaded twice. The folder name is a one-way hash, not your email. Nothing is sent anywhere except Garmin. There is no database, no analytics, no third-party scripts, and Streamlit's usage statistics are switched off. Use *Privacy & data* in the menu to delete the cache at any time.

**Health data is sensitive** (special category data under GDPR Art. 9). Run this app for yourself, on your own machine or a server only you can reach. Don't host it publicly for other people: you would be collecting their Garmin credentials and health data, which needs consent, a legal basis and Garmin's permission.

**Garmin's terms.** Garmin's Terms of Use restrict automated access to its services. Personal, low-volume use for your own data is what this tool is built for: requests are paced, cached aggressively and limited to the date range you choose. You use it at your own risk; Garmin could change or block the sign-in flow at any time.

**Not medical advice.** Training recommendations are rule-based heuristics from sports-science literature (training load, 80/20 intensity, HRV baselines). Listen to your body and to a qualified coach or doctor.
