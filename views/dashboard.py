import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app import coach
from garmin_app.config import SERIES, SPORT_COLORS
from garmin_app.ui import advice_box, data, plot

D = data()
acts, rec, ff = D.acts_all, D.rec, D.ff
today = pd.Timestamp.today().normalize()
monday = today - pd.Timedelta(days=today.weekday())


def window(a: pd.Timestamp, b: pd.Timestamp) -> pd.DataFrame:
    return acts[(acts["date"] >= a) & (acts["date"] < b)]


this_w = window(monday, today + pd.Timedelta(days=1))
last_w = window(monday - pd.Timedelta(days=7), monday - pd.Timedelta(days=7) + (today - monday) + pd.Timedelta(days=1))

# --- today's call ------------------------------------------------------------
call = coach.today_call(rec, ff, an.consecutive_training_days(acts))
c1, c2 = st.columns([2, 3], gap="large")
with c1:
    st.subheader("Today")
    advice_box(call.status, call.session, "  \n".join(f"- {r}" for r in call.reasons) or "Not enough data yet.")
with c2:
    st.subheader("This week so far", help="Compared with the same weekdays of last week.")
    k = st.columns(4)
    k[0].metric("Sessions", len(this_w), len(this_w) - len(last_w))
    k[1].metric("Hours", f"{this_w['hours'].sum():.1f}", f"{this_w['hours'].sum() - last_w['hours'].sum():+.1f}")
    k[2].metric("Distance", f"{this_w['km'].sum():.0f} km", f"{this_w['km'].sum() - last_w['km'].sum():+.0f}")
    k[3].metric("Load", f"{this_w['load'].sum():.0f}", f"{this_w['load'].sum() - last_w['load'].sum():+.0f}")
    if len(ff):
        k = st.columns(4)
        last = ff.iloc[-1]
        prev = ff.iloc[-8] if len(ff) > 8 else last
        k[0].metric("Fitness (CTL)", f"{last['ctl']:.0f}", f"{last['ctl'] - prev['ctl']:+.1f} vs 7d ago")
        k[1].metric("Fatigue (ATL)", f"{last['atl']:.0f}", f"{last['atl'] - prev['atl']:+.1f}", delta_color="inverse")
        k[2].metric("Form (TSB)", f"{last['tsb']:+.0f}")
        k[3].metric("Load ratio", f"{last['acwr']:.2f}", help="Acute:chronic workload ratio. Sweet spot 0.8-1.3.")

# --- body ----------------------------------------------------------------------
if len(rec):
    st.subheader("Body, last night")
    r = rec.dropna(subset=["sleep_h", "hrv", "rhr"], how="all")
    if len(r):
        row, base = r.iloc[-1], r.tail(29).iloc[:-1]
        k = st.columns(6)

        def m(col, label, val, fmt, inverse=False):
            b = base[val].mean() if val in base else np.nan
            v = row.get(val, np.nan)
            col.metric(label, "-" if pd.isna(v) else fmt.format(v),
                       None if pd.isna(v) or pd.isna(b) else f"{v - b:+.1f} vs 4-wk avg",
                       delta_color="inverse" if inverse else "normal")

        m(k[0], "Sleep", "sleep_h", "{:.1f} h")
        m(k[1], "Sleep score", "sleep_score", "{:.0f}")
        m(k[2], "HRV", "hrv", "{:.0f} ms")
        m(k[3], "Resting HR", "rhr", "{:.0f} bpm", inverse=True)
        m(k[4], "Body Battery max", "bb_high", "{:.0f}")
        m(k[5], "Stress (yesterday)", "stress", "{:.0f}", inverse=True)

# --- charts --------------------------------------------------------------------
left, right = st.columns(2, gap="large")
with left:
    w = an.weekly(acts[acts["date"] > today - pd.Timedelta(weeks=16)])
    if len(w):
        fig = px.bar(w, x="week_start", y="hours", color="sport", color_discrete_map=SPORT_COLORS,
                     title="Weekly hours, last 16 weeks", labels={"week_start": "", "hours": "hours"})
        fig.update_traces(marker_line_width=0)
        plot(fig, height=320)
with right:
    if len(ff):
        f = ff[ff.index > today - pd.Timedelta(days=120)]
        fig = go.Figure()
        fig.add_scatter(x=f.index, y=f["ctl"], name="Fitness (CTL)", line_color=SERIES[0])
        fig.add_scatter(x=f.index, y=f["atl"], name="Fatigue (ATL)", line_color=SERIES[1])
        fig.update_layout(title="Fitness vs fatigue, last 4 months")
        plot(fig, height=320, unified=True)

# --- top advice ----------------------------------------------------------------
adv = coach.advise(acts, rec, ff)
if adv:
    st.subheader("Top things to know")
    for a in adv[:4]:
        advice_box(a.status, a.title, a.why)
    st.page_link("views/coach.py", label="All advice and a 7-day plan", icon=":material/arrow_forward:")
