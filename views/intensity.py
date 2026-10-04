import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app.config import SPORT_COLORS, ZONE_COLORS, ZONE_NAMES
from garmin_app.ui import data, need, plot

D = data()
need(D.acts)
acts = D.acts

split = an.intensity_split(acts)
k = st.columns(4)
k[0].metric("Easy (Z1-2)", f"{split['low']:.0f}%", help="Target ~80% for endurance athletes")
k[1].metric("Moderate (Z3)", f"{split['mid']:.0f}%", help="The 'grey zone'. Keep it small.")
k[2].metric("Hard (Z4-5)", f"{split['high']:.0f}%", help="~10-20% is typical")
k[3].metric("Distribution", an.classify_distribution(split))

c1, c2 = st.columns([2, 3], gap="large")
with c1:
    z = an.zone_hours(acts)
    fig = go.Figure(go.Bar(x=z.values, y=ZONE_NAMES, orientation="h", marker_color=ZONE_COLORS,
                           text=[f"{v:.1f} h" for v in z.values], textposition="outside"))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title="Time in HR zones")
    plot(fig, height=320, legend=False)
with c2:
    d = acts.assign(week_start=acts["date"] - pd.to_timedelta(acts["date"].dt.weekday, unit="D"))
    w = d.groupby("week_start")[an.ZONES].sum()
    w = w.div(w.sum(axis=1).replace(0, pd.NA), axis=0) * 100
    fig = go.Figure()
    for i, zc in enumerate(an.ZONES):
        fig.add_bar(x=w.index, y=w[zc], name=ZONE_NAMES[i].split()[0], marker_color=ZONE_COLORS[i])
    fig.add_hline(y=80, line_dash="dot", line_color="gray", annotation_text="80%")
    fig.update_layout(barmode="stack", title="Weekly zone share (%)")
    plot(fig, height=320)

st.subheader("Zone split per sport")
by = acts.groupby("sport")[an.ZONES].sum()
by = by[by.sum(axis=1) > 0]
if len(by):
    pct = by.div(by.sum(axis=1), axis=0).mul(100).reset_index().melt(id_vars="sport", var_name="zone", value_name="pct")
    pct["zone"] = pct["zone"].map(dict(zip(an.ZONES, [n.split()[0] for n in ZONE_NAMES], strict=True)))
    fig = px.bar(pct, y="sport", x="pct", color="zone", orientation="h",
                 color_discrete_sequence=ZONE_COLORS, labels={"pct": "% of time", "sport": ""})
    plot(fig, height=60 + 50 * len(by))

c1, c2 = st.columns(2, gap="large")
with c1:
    st.subheader("Average HR vs duration")
    h = acts.dropna(subset=["avg_hr"])
    fig = px.scatter(h, x="hours", y="avg_hr", color="sport", color_discrete_map=SPORT_COLORS,
                     hover_data={"name": True, "date": "|%d %b %Y"}, labels={"hours": "hours", "avg_hr": "avg HR"})
    fig.update_traces(marker={"size": 8, "line": {"width": 1, "color": "white"}})
    plot(fig, height=340)
with c2:
    st.subheader("Hard sessions per week")
    hard = acts[(acts["z4"].fillna(0) + acts["z5"].fillna(0)) * 60 >= 10]
    if len(hard):
        hw = hard.assign(week_start=hard["date"] - pd.to_timedelta(hard["date"].dt.weekday, unit="D")).groupby("week_start").size()
        fig = go.Figure(go.Bar(x=hw.index, y=hw.values, marker_color=ZONE_COLORS[3]))
        fig.add_hline(y=2, line_dash="dot", line_color="gray", annotation_text="2 / week is plenty for most")
        plot(fig, height=340, legend=False)
        st.caption("A session counts as hard with 10+ minutes in Z4-Z5.")
    else:
        st.caption("No sessions with 10+ min in Z4-Z5 in range.")
