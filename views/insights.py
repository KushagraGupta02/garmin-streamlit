import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_app import analytics as an
from garmin_app.config import SERIES, STATUS_COLORS
from garmin_app.ui import data, need, plot

D = data()
need(D.rec, "health data")

st.caption(
    "Spearman correlations between your own daily metrics. |r| > 0.3 is a meaningful pattern, "
    "< 0.1 is noise. Correlation is not causation, but it shows what's worth experimenting with."
)

cor = an.lagged_correlations(D.rec, D.ff)
if len(cor):
    cor = cor.sort_values("r")
    colors = [STATUS_COLORS["critical"] if r < -0.1 else STATUS_COLORS["good"] if r > 0.1 else "gray" for r in cor["r"]]
    fig = go.Figure(go.Bar(x=cor["r"], y=cor["relationship"], orientation="h", marker_color=colors,
                           text=cor["r"], textposition="outside", customdata=cor["n"],
                           hovertemplate="%{y}<br>r = %{x}<br>n = %{customdata} days<extra></extra>"))
    fig.update_xaxes(range=[-1, 1], zeroline=True, zerolinecolor="gray")
    plot(fig, height=60 + 38 * len(cor), legend=False)
else:
    st.info("Need at least 14 days with both values to compute relationships.")

st.subheader("Explore any pair")
rec = D.rec.set_index("date").join(D.ff[["load", "ctl", "atl", "tsb"]], how="left")
rec["load_yday"] = rec["load"].shift(1)
num = [c for c in rec.columns if rec[c].dtype.kind == "f" and rec[c].notna().sum() >= 10 and not c.endswith(("_z", "_base"))]
c1, c2, c3 = st.columns(3)
x = c1.selectbox("X", num, index=num.index("sleep_h") if "sleep_h" in num else 0)
y = c2.selectbox("Y", num, index=num.index("hrv") if "hrv" in num else 1)
lag = c3.number_input("Shift X by days (X earlier)", 0, 7, 0)
d = rec[[x]].shift(lag).join(rec[[y]], rsuffix="_y").dropna()
if len(d) >= 5:
    yy = y if y != x else f"{y}_y"
    r = an.spearman(d[x], d[yy])
    fig = px.scatter(d.reset_index(), x=x, y=yy, color_discrete_sequence=[SERIES[0]], hover_data={"date": "|%d %b %Y"})
    fig.update_traces(marker={"size": 8, "opacity": 0.6, "line": {"width": 1, "color": "white"}})
    fig.update_layout(title=f"r = {r:.2f}  (n = {len(d)})")
    plot(fig, height=380, legend=False)

st.subheader("Training days vs rest days")
act_days = set(D.acts_all["date"])
r2 = D.rec.copy()
r2["next_day_after"] = (r2["date"] - pd.Timedelta(days=1)).isin(act_days).map({True: "after training day", False: "after rest day"})
cmp = r2.groupby("next_day_after")[["hrv", "rhr", "sleep_score", "bb_high", "stress"]].mean().round(1).T
st.dataframe(cmp, width="stretch")
