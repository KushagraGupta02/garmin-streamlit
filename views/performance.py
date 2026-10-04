import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app.config import SERIES, SPORT_COLORS
from garmin_app.ui import data, need, plot

D = data()
need(D.acts)
acts = D.acts

# --- race predictions ------------------------------------------------------------
rp = D.extras.get("race_predictions") or {}
if isinstance(rp, list):
    rp = rp[-1] if rp else {}
preds = {k: rp.get(f) for k, f in [("5K", "time5K"), ("10K", "time10K"), ("Half", "timeHalfMarathon"), ("Marathon", "timeMarathon")]}
if any(preds.values()):
    st.subheader("Garmin race predictions")
    cols = st.columns(4)
    for col, (k, v) in zip(cols, preds.items(), strict=True):
        if v:
            col.metric(k, an.fmt_hms(v), help=f"{an.fmt_pace(v / 60 / an.RACE_DISTANCES[k])}")

# --- VO2max --------------------------------------------------------------------
vo2 = acts.dropna(subset=["vo2max"])
c1, c2 = st.columns(2, gap="large")
with c1:
    st.subheader("VO2max")
    if len(vo2):
        fig = go.Figure(go.Scatter(x=vo2["date"], y=vo2["vo2max"], mode="lines+markers", line={"color": SERIES[0], "shape": "hv"},
                                   marker={"size": 6}, name="VO2max"))
        plot(fig, height=300, legend=False)
    else:
        st.caption("Your watch has not reported VO2max for activities in range.")
with c2:
    st.subheader("Aerobic efficiency (runs)")
    ef = an.efficiency_factor(acts)
    if len(ef):
        fig = go.Figure()
        fig.add_scatter(x=ef["date"], y=ef["ef"], mode="markers", name="session", marker={"size": 7, "color": SERIES[0], "opacity": 0.45},
                        customdata=ef[["name", "km", "avg_hr"]], hovertemplate="%{customdata[0]}<br>%{customdata[1]:.1f} km @ %{customdata[2]:.0f} bpm<br>EF %{y:.2f}<extra></extra>")
        fig.add_scatter(x=ef["date"], y=ef["ef_trend"], name="6-week median", line_color=SERIES[1])
        fig.update_yaxes(title="m/min per bpm")
        plot(fig, height=300)
        st.caption("Speed per heartbeat on easy and steady runs (hard sessions excluded). Up = fitter.")
    else:
        st.caption("Needs runs with heart rate.")

# --- pace -----------------------------------------------------------------------
runs = acts[(acts["sport"] == "Run") & (acts["pace_min_km"].between(2.5, 12))]
if len(runs):
    st.subheader("Running pace")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        fig = px.scatter(runs, x="date", y="pace_min_km", size="km", color="avg_hr", color_continuous_scale="Blues",
                         hover_data={"name": True, "km": ":.1f"}, labels={"pace_min_km": "min/km", "date": "", "avg_hr": "avg HR"})
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(title="Pace over time (bigger = longer)")
        plot(fig, height=340)
    with c2:
        r = runs.dropna(subset=["avg_hr"]).copy()
        if len(r) >= 5:
            r["hr_band"] = pd.cut(r["avg_hr"], bins=range(100, 200, 10), right=False).astype(str)
            r["half"] = r["date"].apply(lambda d: "Recent half" if d >= r["date"].median() else "Earlier half")
            g = r.groupby(["hr_band", "half"], observed=True)["pace_min_km"].median().reset_index()
            fig = px.bar(g, x="hr_band", y="pace_min_km", color="half", barmode="group",
                         color_discrete_map={"Earlier half": SERIES[1], "Recent half": SERIES[0]},
                         labels={"hr_band": "avg HR band", "pace_min_km": "median min/km"})
            fig.update_layout(title="Pace at the same heart rate: earlier vs recent")
            plot(fig, height=340)

    cad = runs.dropna(subset=["cadence"])
    if len(cad):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            fig = px.scatter(cad, x="speed_kmh", y="cadence", color_discrete_sequence=[SERIES[0]], trendline=None,
                             labels={"speed_kmh": "km/h", "cadence": "steps/min"})
            fig.update_layout(title="Cadence vs speed")
            plot(fig, height=300, legend=False)
        with c2:
            st.metric("Median cadence", f"{cad['cadence'].median():.0f} spm")
            st.caption("Cadence naturally rises with speed. If easy-run cadence is far below ~165 spm, a few % higher (shorter steps) often reduces impact loading.")

    st.subheader("Best efforts near race distances")
    be = an.best_efforts(acts)
    if len(be):
        st.dataframe(be, hide_index=True, width="stretch")
        st.caption("Fastest whole-activity average pace for runs within -3%/+8% of each distance. Garmin's own PRs are on the Records page.")

# --- cycling --------------------------------------------------------------------
bike = acts[(acts["sport"] == "Bike") & acts["avg_power"].notna()]
if len(bike):
    st.subheader("Cycling power")
    fig = px.scatter(bike, x="date", y="avg_power", size="hours", color_discrete_sequence=[SPORT_COLORS["Bike"]],
                     labels={"avg_power": "avg W", "date": ""}, hover_data={"name": True})
    plot(fig, height=300, legend=False)
