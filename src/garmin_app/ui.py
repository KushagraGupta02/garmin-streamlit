"""Shared Streamlit plumbing: data loading, sidebar filters, chart styling."""

import datetime as dt
from dataclasses import dataclass
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app.config import SPORT_COLORS, SPORT_GROUPS, STATUS_COLORS, STATUS_ICONS
from garmin_app.sources import load_bundle
from garmin_app.transform import activities_df, daily_df, estimate_hr_bounds


@dataclass
class Data:
    acts_all: pd.DataFrame
    acts: pd.DataFrame  # filtered by sidebar
    daily: pd.DataFrame
    rec: pd.DataFrame
    ff: pd.DataFrame  # fitness/fatigue on ALL activities
    extras: dict[str, Any]
    hr_rest: float
    hr_max: float
    start: pd.Timestamp
    end: pd.Timestamp


def _settings() -> tuple[int, int]:
    sb = st.sidebar
    sb.caption(f"Signed in as **{st.session_state.get('label', '?')}**")
    years = sb.slider("Activity history (years)", 1, 10, 2, key="years",
                      help="Older years are downloaded once and cached.")
    health = sb.select_slider("Health history (days)", [30, 60, 90, 180, 365], value=90, key="health",
                              help="Sleep/HRV/stress need ~4 requests per day the first time.")
    if sb.button("Refresh today's data", icon=":material/refresh:"):
        st.session_state.pop("bundle", None)
        st.session_state.pop("frames", None)
    return years, health


def data() -> Data:
    years, health = _settings()
    src = st.session_state["source"]
    params = (years, health)
    if st.session_state.get("bundle_params") != params or "bundle" not in st.session_state:
        start = dt.date(dt.date.today().year - years + 1, 1, 1)
        bar = st.progress(0.0, "Loading from Garmin...")
        try:
            bundle = load_bundle(src, start, health, lambda f, m: bar.progress(min(f, 1.0), m))
        except Exception as e:
            name = type(e).__name__
            if "TooManyRequests" in name:
                st.error("Garmin is rate-limiting us. Data fetched so far is cached; try again in a few minutes.")
                st.stop()
            if "Authentication" in name:
                st.error("Your Garmin session expired. Log out (Privacy & data) and sign in again.")
                st.stop()
            raise
        bar.empty()
        st.session_state["bundle"] = bundle
        st.session_state["bundle_params"] = params
        st.session_state.pop("frames", None)

    if "frames" not in st.session_state:
        b = st.session_state["bundle"]
        daily = daily_df(b["days"])
        rest, hmax = estimate_hr_bounds(daily, b["activities"])
        acts = activities_df(b["activities"], rest, hmax)
        st.session_state["frames"] = (acts, daily, an.recovery_frame(daily) if len(daily) > 1 else daily,
                                      an.fitness_fatigue(an.daily_load(acts)), rest, hmax)
    acts, daily, rec, ff, rest, hmax = st.session_state["frames"]

    # filters
    sb = st.sidebar
    sb.divider()
    present = [s for s in SPORT_GROUPS if s in set(acts["sport"])]
    sports = sb.multiselect("Sports", present, default=present, key="sports")
    if len(acts):
        lo, hi = acts["date"].min().date(), dt.date.today()
        rng = sb.date_input("Date range", (max(lo, hi - dt.timedelta(days=365)), hi), min_value=lo, max_value=hi, key="range")
        start, end = (rng if isinstance(rng, tuple) and len(rng) == 2 else (lo, hi))
    else:
        start, end = dt.date.today() - dt.timedelta(days=365), dt.date.today()
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    f = acts[acts["sport"].isin(sports) & (acts["date"] >= start) & (acts["date"] <= end)]
    return Data(acts, f, daily, rec, ff, st.session_state["bundle"]["extras"], rest, hmax, start, end)


# --- charts ---------------------------------------------------------------
def style(fig: go.Figure, height: int = 360, legend: bool = True, unified: bool = False) -> go.Figure:
    has_title = bool(fig.layout.title.text)
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": (40 if has_title else 8) + (28 if legend else 0), "b": 8},
        title={"x": 0, "xanchor": "left", "y": 1, "yref": "container", "yanchor": "top", "pad": {"t": 8}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0, "title": None},
        showlegend=legend,
        hovermode="x unified" if unified else "closest",
        bargap=0.15,
        font={"size": 12},
    )
    fig.update_xaxes(showgrid=False, title=None)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def plot(fig: go.Figure, **kw: Any) -> None:
    st.plotly_chart(style(fig, **kw), width="stretch", config={"displaylogo": False})


def sport_color_map() -> dict[str, str]:
    return SPORT_COLORS


def advice_box(status: str, title: str, body: str) -> None:
    icon = STATUS_ICONS[status]
    fn = {"good": st.success, "warning": st.warning, "serious": st.warning, "critical": st.error, "info": st.info}[status]
    fn(f"**{title}**  \n{body}", icon=icon)


def status_dot(status: str) -> str:
    return f'<span style="color:{STATUS_COLORS[status]}">&#9679;</span>'


def need(df: pd.DataFrame, what: str = "activities") -> None:
    if df is None or len(df) == 0:
        st.info(f"No {what} in the selected range. Widen the date range or sports filter in the sidebar.")
        st.stop()
