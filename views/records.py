import pandas as pd
import streamlit as st

from garmin_app import analytics as an
from garmin_app.ui import data, need

D = data()
need(D.acts)

st.subheader("Your records in the selected range")
st.dataframe(an.records(D.acts), hide_index=True, width="stretch")

st.subheader("Best efforts near race distances")
be = an.best_efforts(D.acts)
if len(be):
    st.dataframe(be, hide_index=True, width="stretch")
else:
    st.caption("No runs near 5K / 10K / half / marathon distance in range.")

prs = D.extras.get("personal_records") or []
if prs:
    st.subheader("Garmin personal records")
    TYPES = {1: "1 km", 2: "1 mile", 3: "5K", 4: "10K", 5: "Half marathon", 6: "Marathon", 7: "Longest run",
             8: "Longest ride", 9: "Total ascent", 10: "Max avg power (20 min)", 12: "Most steps in a day",
             13: "Most steps in a week", 14: "Most steps in a month", 15: "Longest goal streak"}
    rows = []
    for p in prs:
        t = p.get("typeId")
        v = p.get("value")
        label = TYPES.get(t, f"type {t}")
        if t in (1, 2, 3, 4, 5, 6):
            val = an.fmt_hms(v)
        elif t in (7, 8):
            val = f"{v / 1000:.1f} km"
        else:
            val = f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)
        rows.append({"record": label, "value": val, "date": str(p.get("prStartTimeGmtFormatted") or p.get("actStartDateTimeInGMTFormatted") or "")[:10],
                     "activity": p.get("activityName") or ""})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

st.subheader("Top 10 by load")
top = D.acts.nlargest(10, "load")[["date", "name", "sport", "hours", "km", "avg_hr", "load", "te_aerobic"]]
top["date"] = top["date"].dt.date
st.dataframe(top.round(1), hide_index=True, width="stretch")
