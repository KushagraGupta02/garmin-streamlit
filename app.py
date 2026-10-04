"""Garmin Insights: entry point. Run with `streamlit run app.py`."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

st.set_page_config(page_title="Garmin Insights", page_icon=":material/monitor_heart:", layout="wide")

from garmin_app.auth import login_page  # noqa: E402

V = Path(__file__).parent / "views"


def main() -> None:
    if "source" not in st.session_state:
        login_page()
        return

    pages = {
        "Today": [
            st.Page(V / "dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
            st.Page(V / "coach.py", title="Coach: what to train", icon=":material/sports:"),
        ],
        "Training": [
            st.Page(V / "load.py", title="Training load & form", icon=":material/trending_up:"),
            st.Page(V / "intensity.py", title="Intensity & HR zones", icon=":material/favorite:"),
            st.Page(V / "performance.py", title="Performance", icon=":material/speed:"),
            st.Page(V / "statistics.py", title="Statistics", icon=":material/bar_chart:"),
        ],
        "Body": [
            st.Page(V / "recovery.py", title="Sleep & recovery", icon=":material/bedtime:"),
            st.Page(V / "insights.py", title="What affects what", icon=":material/insights:"),
        ],
        "History": [
            st.Page(V / "calendar.py", title="Calendar & habits", icon=":material/calendar_month:"),
            st.Page(V / "records.py", title="Records", icon=":material/emoji_events:"),
            st.Page(V / "activities.py", title="Activities & export", icon=":material/table:"),
        ],
        "Account": [
            st.Page(V / "privacy.py", title="Privacy & data", icon=":material/shield:"),
        ],
    }
    page = st.navigation(pages)
    if st.session_state.get("user_key") == "demo":
        st.sidebar.info("Demo mode: synthetic data", icon=":material/science:")
    st.title(page.title)
    page.run()


main()
