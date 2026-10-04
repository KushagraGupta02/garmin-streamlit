import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app.config import SERIES, SPORT_COLORS, STATUS_COLORS
from garmin_app.ui import data, need, plot

D = data()
need(D.acts)
ff = D.ff[(D.ff.index >= D.start) & (D.ff.index <= D.end)]

st.caption(
    "Load per activity is Garmin's *Training Load* (EPOC-based). When missing, it is estimated with "
    f"Banister TRIMP from average HR (resting {D.hr_rest:.0f}, max {D.hr_max:.0f} bpm, estimated from your data)."
)

fig = go.Figure()
fig.add_bar(x=ff.index, y=ff["load"], name="Daily load", marker_color="rgba(128,128,128,0.35)")
fig.add_scatter(x=ff.index, y=ff["ctl"], name="Fitness (CTL, 42d)", line_color=SERIES[0])
fig.add_scatter(x=ff.index, y=ff["atl"], name="Fatigue (ATL, 7d)", line_color=SERIES[1])
fig.update_layout(title="Fitness and fatigue")
plot(fig, height=380, unified=True)

c1, c2 = st.columns(2, gap="large")
with c1:
    fig = go.Figure()
    for lo, hi, col, lab in [(-200, -30, "critical", "overreaching"), (-30, -10, "good", "productive"),
                             (-10, 5, "info", "neutral"), (5, 25, "warning", "fresh"), (25, 200, "serious", "detraining")]:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=STATUS_COLORS[col], opacity=0.08, line_width=0,
                      annotation_text=lab, annotation_position="top left", annotation_font_size=10)
    fig.add_scatter(x=ff.index, y=ff["tsb"], name="Form", line_color=SERIES[0])
    rng = ff["tsb"].dropna()
    if len(rng):
        fig.update_yaxes(range=[min(-40, rng.min() - 5), max(30, rng.max() + 5)])
    fig.update_layout(title="Form (TSB = fitness - fatigue)")
    plot(fig, height=320, legend=False)
with c2:
    fig = go.Figure()
    fig.add_hrect(y0=0.8, y1=1.3, fillcolor=STATUS_COLORS["good"], opacity=0.1, line_width=0,
                  annotation_text="sweet spot", annotation_position="top left", annotation_font_size=10)
    fig.add_hrect(y0=1.5, y1=3, fillcolor=STATUS_COLORS["critical"], opacity=0.08, line_width=0,
                  annotation_text="danger", annotation_position="top left", annotation_font_size=10)
    fig.add_scatter(x=ff.index, y=ff["acwr"].clip(upper=2.5), name="ACWR", line_color=SERIES[0])
    fig.update_yaxes(range=[0, 2.2])
    fig.update_layout(title="Acute:chronic load ratio")
    plot(fig, height=320, legend=False)

c1, c2 = st.columns(2, gap="large")
with c1:
    fig = go.Figure()
    fig.add_hline(y=2, line_dash="dot", line_color=STATUS_COLORS["warning"], annotation_text="2.0")
    fig.add_scatter(x=ff.index, y=ff["monotony"], line_color=SERIES[0], name="Monotony")
    fig.update_layout(title="Training monotony (7-day)")
    plot(fig, height=300, legend=False)
with c2:
    fig = go.Figure(go.Scatter(x=ff.index, y=ff["strain"], line_color=SERIES[0], name="Strain"))
    fig.update_layout(title="Training strain (weekly load x monotony)")
    plot(fig, height=300, legend=False)

st.subheader("Weekly load by sport")
w = an.weekly(D.acts)
fig = px.bar(w, x="week_start", y="load", color="sport", color_discrete_map=SPORT_COLORS, labels={"week_start": ""})
plot(fig, height=320)

rr = an.ramp_rate(D.acts_all, "Run")
if len(rr):
    rr = rr[rr.index >= D.start]
    st.subheader("Running: weekly distance and the 10% rule")
    colors = [STATUS_COLORS["critical"] if c > 15 and a > 5 else STATUS_COLORS["info"] for c, a in zip(rr["change_pct"].fillna(0), rr["avg_prev"].fillna(0), strict=True)]
    fig = go.Figure()
    fig.add_bar(x=rr.index, y=rr["km"], marker_color=colors, name="km/week",
                customdata=rr["change_pct"].round(0), hovertemplate="%{x|%d %b %Y}: %{y:.1f} km (%{customdata:+}% vs 4-wk avg)<extra></extra>")
    fig.add_scatter(x=rr.index, y=rr["avg_prev"] * 1.1, name="+10% over prior 4-wk avg", line={"dash": "dot", "color": "gray"})
    plot(fig, height=320)
    st.caption("Red bars: more than 15% above your previous 4-week average.")

st.subheader("Garmin Training Effect")
te = D.acts.dropna(subset=["te_aerobic"])
if len(te):
    fig = px.scatter(te, x="te_aerobic", y="te_anaerobic", color="sport", color_discrete_map=SPORT_COLORS,
                     hover_data={"name": True, "date": "|%d %b %Y"}, labels={"te_aerobic": "Aerobic TE", "te_anaerobic": "Anaerobic TE"})
    fig.update_traces(marker={"size": 8, "line": {"width": 1, "color": "white"}})
    plot(fig, height=360)
    st.caption("TE 1-2: recovery, 2-3: maintaining, 3-4: improving, 4-5: highly improving, 5: overreaching.")
