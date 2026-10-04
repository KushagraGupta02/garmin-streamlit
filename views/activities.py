import io

import pandas as pd
import streamlit as st

from garmin_app.ui import data, need

D = data()
need(D.acts)

q = st.text_input("Search name or location", placeholder="e.g. intervals")
df = D.acts.copy()
if q:
    m = df["name"].str.contains(q, case=False, na=False) | df["location"].str.contains(q, case=False, na=False)
    df = df[m]

show = df.sort_values("start", ascending=False)[
    ["start", "name", "type", "km", "hours", "pace_min_km", "speed_kmh", "elev_m", "avg_hr", "max_hr", "load", "te_aerobic", "te_anaerobic", "vo2max", "calories"]
].round(2)
st.caption(f"{len(show)} activities")
st.dataframe(
    show,
    hide_index=True,
    width="stretch",
    height=560,
    column_config={
        "start": st.column_config.DatetimeColumn("start", format="YYYY-MM-DD HH:mm"),
        "hours": st.column_config.NumberColumn("h", format="%.2f"),
        "pace_min_km": st.column_config.NumberColumn("min/km", format="%.2f"),
    },
)

st.subheader("Export")
st.caption("Exports stay on your device. They contain personal health data: store them carefully.")
c1, c2, c3 = st.columns(3)
c1.download_button("Activities (CSV)", df.to_csv(index=False).encode(), "garmin_activities.csv", "text/csv", icon=":material/download:")
c2.download_button("Daily health (CSV)", D.daily.to_csv(index=False).encode(), "garmin_daily.csv", "text/csv", icon=":material/download:")
try:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as xw:
        df.to_excel(xw, sheet_name="activities", index=False)
        D.daily.to_excel(xw, sheet_name="daily", index=False)
    c3.download_button("Both (Excel)", buf.getvalue(), "garmin_export.xlsx", icon=":material/download:")
except ImportError:
    c3.caption("Install openpyxl for Excel export.")
