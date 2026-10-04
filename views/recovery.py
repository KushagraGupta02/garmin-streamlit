import numpy as np
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app.config import SERIES, STATUS_COLORS, ZONE_COLORS
from garmin_app.ui import data, need, plot

D = data()
rec = D.rec.copy()
need(rec, "health data")
rec["recovery"] = rec.apply(an.recovery_score, axis=1)

k = st.columns(5)
t = rec.tail(7)
k[0].metric("Sleep, 7-night avg", f"{t['sleep_h'].mean():.1f} h")
k[1].metric("Sleep score, 7-night", f"{t['sleep_score'].mean():.0f}")
k[2].metric("HRV, 7-night", f"{t['hrv'].mean():.0f} ms")
k[3].metric("Resting HR, 7-day", f"{t['rhr'].mean():.0f} bpm")
k[4].metric("Recovery score, today", f"{rec['recovery'].iloc[-1]:.0f}" if not np.isnan(rec["recovery"].iloc[-1]) else "-")

# --- recovery composite ---------------------------------------------------------
fig = go.Figure()
colors = [STATUS_COLORS["critical"] if v < 35 else STATUS_COLORS["warning"] if v < 55 else STATUS_COLORS["good"] if v >= 70 else "rgba(128,128,128,0.45)"
          for v in rec["recovery"].fillna(50)]
fig.add_bar(x=rec["date"], y=rec["recovery"], marker_color=colors, name="Recovery")
if rec["readiness"].notna().any():
    fig.add_scatter(x=rec["date"], y=rec["readiness"], name="Garmin Training Readiness", line={"color": "gray", "dash": "dot", "width": 1.5})
fig.update_layout(title="Recovery score (green >= 70, gray 55-70, yellow 35-55, red < 35)")
plot(fig, height=300, unified=True)

# --- HRV ------------------------------------------------------------------------
c1, c2 = st.columns(2, gap="large")
with c1:
    fig = go.Figure()
    if rec["hrv_low"].notna().any():
        fig.add_scatter(x=rec["date"], y=rec["hrv_high"], line={"width": 0}, showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=rec["date"], y=rec["hrv_low"], fill="tonexty", fillcolor="rgba(12,163,12,0.12)", line={"width": 0},
                        name="Garmin balanced range")
    fig.add_scatter(x=rec["date"], y=rec["hrv"], mode="markers", marker={"size": 5, "color": SERIES[0], "opacity": 0.5}, name="nightly")
    fig.add_scatter(x=rec["date"], y=rec["hrv"].rolling(7, min_periods=3).mean(), name="7-day avg", line_color=SERIES[0])
    fig.update_layout(title="Overnight HRV (ms)")
    plot(fig, height=320)
with c2:
    fig = go.Figure()
    fig.add_scatter(x=rec["date"], y=rec["rhr"], mode="markers", marker={"size": 5, "color": SERIES[1], "opacity": 0.5}, name="daily")
    fig.add_scatter(x=rec["date"], y=rec["rhr"].rolling(7, min_periods=3).mean(), name="7-day avg", line_color=SERIES[1])
    fig.update_layout(title="Resting heart rate (bpm)")
    plot(fig, height=320)

# --- sleep ----------------------------------------------------------------------
st.subheader("Sleep")
fig = go.Figure()
for col, name, c in [("deep_h", "Deep", ZONE_COLORS[4]), ("light_h", "Light", ZONE_COLORS[1]), ("rem_h", "REM", SERIES[2]), ("awake_h", "Awake", SERIES[1])]:
    fig.add_bar(x=rec["date"], y=rec[col], name=name, marker_color=c)
fig.add_hline(y=7, line_dash="dot", line_color="gray", annotation_text="7 h")
fig.update_layout(barmode="stack", title="Sleep stages (hours)")
plot(fig, height=320, unified=True)

c1, c2 = st.columns(2, gap="large")
with c1:
    b = rec.dropna(subset=["bedtime", "sleep_score"])
    if len(b) >= 5:
        fig = go.Figure(go.Scatter(x=b["bedtime"], y=b["sleep_score"], mode="markers", marker={"size": 8, "color": SERIES[0], "opacity": 0.6, "line": {"width": 1, "color": "white"}},
                                   customdata=b["date"].dt.strftime("%d %b"), hovertemplate="%{customdata}: bed %{x:.1f}h, score %{y}<extra></extra>"))
        fig.update_xaxes(title="bedtime (hours from midnight, -1 = 23:00)")
        fig.update_layout(title="Bedtime vs sleep score")
        plot(fig, height=300, legend=False)
with c2:
    rec["weekday"] = rec["date"].dt.day_name().str[:3]
    wd = rec.groupby("weekday", sort=False)[["sleep_h"]].mean().reindex(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    fig = go.Figure(go.Bar(x=wd.index, y=wd["sleep_h"], marker_color=SERIES[0], text=wd["sleep_h"].round(1), textposition="outside"))
    fig.update_layout(title="Average sleep by night (date = morning)")
    plot(fig, height=300, legend=False)

# --- stress & body battery -------------------------------------------------------
st.subheader("Stress and Body Battery")
c1, c2 = st.columns(2, gap="large")
with c1:
    fig = go.Figure()
    fig.add_scatter(x=rec["date"], y=rec["bb_high"], name="Morning high", line_color=SERIES[0])
    fig.add_scatter(x=rec["date"], y=rec["bb_low"], name="Daily low", line_color=SERIES[1])
    fig.update_layout(title="Body Battery")
    plot(fig, height=300, unified=True)
with c2:
    fig = go.Figure(go.Bar(x=rec["date"], y=rec["stress"], marker_color=[STATUS_COLORS["serious"] if v > 40 else SERIES[0] for v in rec["stress"].fillna(0)]))
    fig.update_layout(title="Average daily stress (orange > 40)")
    plot(fig, height=300, legend=False)

with st.expander("Other daily metrics"):
    c1, c2, c3 = st.columns(3)
    for col, (field, title) in zip([c1, c2, c3], [("steps", "Steps"), ("spo2", "Avg SpO2 (%)"), ("respiration", "Waking respiration (brpm)")], strict=True):
        with col:
            if rec[field].notna().any():
                fig = go.Figure(go.Scatter(x=rec["date"], y=rec[field], line_color=SERIES[0]))
                fig.update_layout(title=title)
                plot(fig, height=240, legend=False)
