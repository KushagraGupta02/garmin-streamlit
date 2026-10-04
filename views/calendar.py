import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app.config import SERIES
from garmin_app.ui import data, need, plot

D = data()
need(D.acts)
acts = D.acts

s = an.streaks(acts)
k = st.columns(4)
k[0].metric("Current streak", f"{s['current']} days")
k[1].metric("Longest streak", f"{s['longest']} days")
k[2].metric("Longest break", f"{s['rest_gap_max']} days")
days = (D.end - D.start).days + 1
k[3].metric("Active days in range", f"{acts['date'].nunique()}", f"{100 * acts['date'].nunique() / days:.0f}% of days")

# --- GitHub-style heatmap for each year ------------------------------------------
metric = st.segmented_control("Color by", ["hours", "load", "km"], default="hours") or "hours"
daily = acts.groupby("date")[metric].sum()
for year in sorted(acts["year"].unique(), reverse=True):
    idx = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    v = daily.reindex(idx, fill_value=0)
    week = ((idx - pd.Timestamp(f"{year}-01-01")).days + pd.Timestamp(f"{year}-01-01").weekday()) // 7
    z = np.full((7, week.max() + 1), np.nan)
    txt = np.full(z.shape, "", dtype=object)
    for d, w, val in zip(idx, week, v.values, strict=True):
        z[d.weekday(), w] = val if val > 0 else np.nan
        txt[d.weekday(), w] = f"{d:%a %d %b}: {val:.1f}"
    fig = go.Figure(go.Heatmap(z=z, text=txt, hoverinfo="text", colorscale=[[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]],
                               xgap=2, ygap=2, showscale=False))
    fig.update_yaxes(tickvals=list(range(7)), ticktext=["Mon", "", "Wed", "", "Fri", "", "Sun"], autorange="reversed", showgrid=False)
    months = pd.date_range(f"{year}-01-01", periods=12, freq="MS")
    fig.update_xaxes(tickvals=[((m - pd.Timestamp(f"{year}-01-01")).days + pd.Timestamp(f"{year}-01-01").weekday()) // 7 for m in months],
                     ticktext=[m.strftime("%b") for m in months], showgrid=False)
    fig.update_layout(title=f"{year}: {v.sum():,.0f} {metric}, {int((v > 0).sum())} active days")
    plot(fig, height=200, legend=False)

# --- when do you train ---------------------------------------------------------
st.subheader("When you train")
c1, c2 = st.columns(2, gap="large")
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
with c1:
    wd = acts.groupby("weekday")["hours"].sum().reindex(order).fillna(0) / max(1, days / 7)
    fig = go.Figure(go.Bar(x=[d[:3] for d in order], y=wd.values, marker_color=SERIES[0]))
    fig.update_layout(title="Average hours per weekday")
    plot(fig, height=280, legend=False)
with c2:
    hm = acts.pivot_table(index="weekday", columns="hour", values="id", aggfunc="count").reindex(order)
    hm = hm.reindex(columns=range(24))
    fig = go.Figure(go.Heatmap(z=hm.values, x=list(range(24)), y=[d[:3] for d in order],
                               colorscale=[[0, "#cde2fb"], [1, "#0d366b"]], xgap=1, ygap=1, showscale=False,
                               hovertemplate="%{y} %{x}:00 - %{z} sessions<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title="Session start time")
    plot(fig, height=280, legend=False)
