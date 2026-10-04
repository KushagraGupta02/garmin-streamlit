from pathlib import Path

import streamlit as st

from garmin_app.auth import SAVED, logout
from garmin_app.sources import GarminSource

src = st.session_state.get("source")

st.markdown((Path(__file__).parents[1] / "src" / "garmin_app" / "privacy.md").read_text())

st.subheader("Your data on this machine")
if isinstance(src, GarminSource):
    k = st.columns(3)
    k[0].metric("Cached files", src.cache.file_count())
    k[1].metric("Cache size", f"{src.cache.size_bytes() / 1e6:.1f} MB")
    k[2].metric("Saved login token", "yes" if SAVED.exists() and any(SAVED.glob("*.json")) else "no")
    st.code(str(src.cache.dir), language=None)
else:
    st.caption("Demo mode: nothing is stored.")

st.subheader("Sign out")
wipe = st.checkbox("Also delete my cached Garmin data", value=False)
if st.button("Log out", type="primary", icon=":material/logout:"):
    logout(delete_cache=wipe)
    st.rerun()
