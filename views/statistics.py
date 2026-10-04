import datetime as dt

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_app.config import SERIES, SPORT_COLORS
from garmin_app.ui import data, need, plot

D = data()
need(D.acts)
acts = D.acts

MEASURES = {
    "Hours": ("hours", "sum"),
    "Distance (km)": ("km", "sum"),
    "Sessions": ("id", "count"),
    "Elevation (m)": ("elev_m", "sum"),
    "Training load": ("load", "sum"),
    "Calories": ("calories", "sum"),
    "Avg HR": ("avg_hr", "mean"),
    "Avg speed (km/h)": ("speed_kmh", "mean"),
}
FREQ = {"Week": "W-MON", "Month": "MS", "Quarter": "QS", "Year": "YS"}

c1, c2, c3 = st.columns(3)
measure = c1.selectbox("Measure", list(MEASURES))
freq = c2.segmented_control("Group by", list(FREQ), default="Month") or "Month"
split = c3.toggle("Split by sport", value=True)

col, agg = MEASURES[measure]
keys = [pd.Grouper(key="date", freq=FREQ[freq], label="left", closed="left")] + (["sport"] if split else [])
g = acts.groupby(keys)[col].agg(agg).reset_index().rename(columns={col: measure})
if agg == "mean":
    fig = px.line(g, x="date", y=measure, color="sport" if split else None, color_discrete_map=SPORT_COLORS, markers=True)
else:
    fig = px.bar(g, x="date", y=measure, color="sport" if split else None, color_discrete_map=SPORT_COLORS,
                 color_discrete_sequence=[SERIES[0]])
plot(fig, height=380, unified=agg == "mean")

# --- year over year ---------------------------------------------------------------
st.subheader("Year over year, cumulative")
c1, c2 = st.columns([1, 3])
ym = c1.selectbox("Measure ", ["Distance (km)", "Hours", "Sessions", "Elevation (m)", "Training load"])
col, agg = MEASURES[ym]
a = D.acts_all[D.acts_all["sport"].isin(acts["sport"].unique())].copy()
a["doy"] = a["date"].dt.dayofyear
a["v"] = 1 if agg == "count" else a[col].fillna(0)
fig = go.Figure()
years = sorted(a["year"].unique())
for y in years:
    s = a[a["year"] == y].groupby("doy")["v"].sum().cumsum()
    current = y == dt.date.today().year
    fig.add_scatter(x=s.index, y=s.values, name=str(y), mode="lines",
                    line={"color": SERIES[0] if current else "rgba(128,128,128,0.45)", "width": 3 if current else 1.5})
    if not current and len(years) <= 6:
        fig.add_annotation(x=s.index[-1], y=s.values[-1], text=str(y), showarrow=False, xanchor="left", font={"size": 10})
fig.update_xaxes(title="day of year")
plot(fig, height=380)

cy = a[a["year"] == dt.date.today().year]
if len(cy):
    doy = dt.date.today().timetuple().tm_yday
    so_far = cy["v"].sum()
    prev = a[(a["year"] == dt.date.today().year - 1) & (a["doy"] <= doy)]["v"].sum()
    k = st.columns(3)
    k[0].metric(f"{ym} this year", f"{so_far:,.0f}", f"{so_far - prev:+,.0f} vs same day last year" if prev else None)
    k[1].metric("Projected full year", f"{so_far / doy * 365:,.0f}")
    k[2].metric("Active days this year", cy["date"].nunique(), f"{100 * cy['date'].nunique() / doy:.0f}% of days")

# --- sport mix --------------------------------------------------------------------
st.subheader("Sport mix")
c1, c2 = st.columns(2, gap="large")
mix = acts.groupby("sport").agg(hours=("hours", "sum"), sessions=("id", "count")).reset_index()
with c1:
    fig = px.bar(mix.sort_values("hours"), x="hours", y="sport", orientation="h", color="sport",
                 color_discrete_map=SPORT_COLORS, text_auto=".0f", labels={"sport": ""})
    plot(fig, height=280, legend=False)
with c2:
    st.dataframe(
        acts.groupby("sport").agg(
            sessions=("id", "count"), hours=("hours", "sum"), km=("km", "sum"),
            avg_hours=("hours", "mean"), avg_hr=("avg_hr", "mean"), elevation=("elev_m", "sum"),
        ).round(1),
        width="stretch",
    )
