import streamlit as st

from garmin_app import analytics as an
from garmin_app import coach
from garmin_app.ui import advice_box, data

D = data()
acts, rec, ff = D.acts_all, D.rec, D.ff

st.caption("Rule-based guidance from your own data. Each card says which number triggered it. Not medical advice.")

call = coach.today_call(rec, ff, an.consecutive_training_days(acts))
st.subheader("Today's session")
advice_box(call.status, call.session, "  \n".join(f"- {r}" for r in call.reasons) or "Not enough data yet.")

adv = coach.advise(acts, rec, ff)
cols = st.columns(3, gap="large")
for col, kind, title in zip(cols, ["do", "avoid", "watch"], ["Do more of", "Avoid / cut back", "Keep an eye on"], strict=True):
    with col:
        st.subheader(title)
        items = [a for a in adv if a.kind == kind]
        if not items:
            st.caption("Nothing flagged.")
        for a in items:
            advice_box(a.status, a.title, f"{a.why}  \n*Rule: {a.rule}*")

st.divider()
plan = coach.week_plan(call, acts, ff)
st.subheader(f"Next 7 days: {plan.attrs['phase']} week, about {plan.attrs['target_h']:.1f} h")
st.caption(
    "Built from your last 4 weeks: Build adds ~10%, Recover cuts ~30%. "
    "Roughly 80% easy, one quality day, one long day, one rest day, strength once."
)
st.dataframe(plan, hide_index=True, width="stretch",
             column_config={"minutes": st.column_config.NumberColumn("min", format="%d")})

with st.expander("How the coach decides"):
    st.markdown(
        """
- **Load ratio (ACWR)**: 7-day vs 42-day exponentially weighted load. 0.8-1.3 is the usual sweet spot; above 1.5 injury risk climbs (Gabbett 2016, Williams 2017).
- **Form (TSB)**: fitness minus fatigue. Below -30 = overreaching, +5 to +25 = fresh / race-ready.
- **Monotony**: mean / SD of daily load over 7 days (Foster 1998). Above 2 means every day looks the same.
- **80/20 intensity**: time in Garmin HR zones grouped as easy (Z1-2), moderate (Z3), hard (Z4-5). Endurance athletes do best with ~80% easy (Seiler).
- **10% rule**: weekly running distance vs your prior 4-week average.
- **Recovery score**: HRV and resting HR as deviations from *your* 28-day baseline, plus sleep score, Body Battery and Garmin Training Readiness.
- **Efficiency factor**: speed per heartbeat on easy runs. Rising over weeks = aerobic fitness improving.
"""
    )
