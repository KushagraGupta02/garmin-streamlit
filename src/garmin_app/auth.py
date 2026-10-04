"""Login, MFA, demo mode and logout.

Privacy rules implemented here:
- The password is only passed to Garmin's SSO and never written anywhere.
- OAuth tokens are kept in memory for the session. Only if the user ticks
  "Remember me" are they written to data/tokens/ (chmod 600), and logout
  deletes them.
"""

import contextlib
import json
import os
from pathlib import Path

import streamlit as st

from garmin_app.cache import DiskCache, user_key
from garmin_app.config import SAVED_META as META
from garmin_app.config import SAVED_TOKENS as SAVED
from garmin_app.demo import DemoSource
from garmin_app.sources import GarminSource


def _set_source(src, key: str, label: str) -> None:
    st.session_state["source"] = src
    st.session_state["user_key"] = key
    st.session_state["label"] = label
    st.session_state.pop("bundle", None)


def _secure_dump(client, path: Path, key: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    client.client.dump(str(path))
    for f in path.glob("*.json"):
        os.chmod(f, 0o600)
    META.write_text(json.dumps({"user_key": key}))
    os.chmod(META, 0o600)


def _finish_login(g, email: str, remember: bool) -> None:
    key = user_key(email)
    if remember:
        _secure_dump(g, SAVED, key)
    name = None
    with contextlib.suppress(Exception):
        name = g.get_full_name()
    _set_source(GarminSource(g, DiskCache(key)), key, name or "Garmin user")


def _resume_saved() -> None:
    from garminconnect import Garmin

    g = Garmin()
    g.login(str(SAVED))
    key = json.loads(META.read_text())["user_key"]
    name = None
    with contextlib.suppress(Exception):
        name = g.get_full_name()
    _set_source(GarminSource(g, DiskCache(key)), key, name or "Garmin user")


def login_page() -> None:
    st.title("Garmin Insights")
    st.caption(
        "Personal training analytics for your Garmin Connect data. Self-hosted, "
        "no database, no tracking. Read the [privacy notes](#privacy) below."
    )

    left, right = st.columns([3, 2], gap="large")
    with right:
        st.subheader("Just looking?")
        st.write("Explore every page with a synthetic athlete. No account needed, nothing leaves your machine.")
        if st.button("Open demo", type="secondary", icon=":material/science:"):
            _set_source(DemoSource(), "demo", "Demo athlete")
            st.rerun()

        if META.exists():
            st.subheader("Saved session")
            st.write("A token from an earlier *Remember me* login is stored on this machine.")
            if st.button("Continue with saved login", icon=":material/login:"):
                try:
                    _resume_saved()
                    st.rerun()
                except Exception as e:
                    st.error(f"Saved login no longer works ({type(e).__name__}). Please sign in again.")

    with left:
        pending = st.session_state.get("mfa_pending")
        if pending:
            st.subheader("Two-factor code")
            with st.form("mfa"):
                code = st.text_input("Code from your authenticator app / email", max_chars=8)
                ok = st.form_submit_button("Verify", type="primary")
            if ok and code:
                g, state, email, remember = pending
                try:
                    g.resume_login(state, code.strip())
                    st.session_state.pop("mfa_pending")
                    _finish_login(g, email, remember)
                    st.rerun()
                except Exception as e:
                    st.error(f"Verification failed: {type(e).__name__}")
            if st.button("Cancel"):
                st.session_state.pop("mfa_pending")
                st.rerun()
            return

        st.subheader("Sign in with Garmin Connect")
        with st.form("login"):
            email = st.text_input("Email", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            c1, c2 = st.columns(2)
            remember = c1.checkbox("Remember me on this machine", help="Stores an OAuth token (not your password) in data/tokens/. Logout deletes it.")
            is_cn = c2.checkbox("Garmin China account")
            ok = st.form_submit_button("Sign in", type="primary")
        if ok:
            if not email or not password:
                st.warning("Enter email and password.")
                return
            from garminconnect import Garmin

            g = Garmin(email=email, password=password, is_cn=is_cn, return_on_mfa=True)
            with st.spinner("Signing in to Garmin..."):
                try:
                    status, state = g.login()
                except Exception as e:
                    st.error(f"Login failed: {type(e).__name__}. Check credentials, or try again in a few minutes if Garmin is rate-limiting.")
                    return
            if status == "needs_mfa":
                st.session_state["mfa_pending"] = (g, state, email, remember)
                st.rerun()
            _finish_login(g, email, remember)
            st.rerun()

    st.divider()
    st.subheader("Privacy", anchor="privacy")
    st.markdown((Path(__file__).parent / "privacy.md").read_text())


def logout(delete_cache: bool = False) -> None:
    src = st.session_state.get("source")
    if isinstance(src, GarminSource):
        with contextlib.suppress(Exception):
            src.client.logout(str(SAVED) if SAVED.exists() else None)
        if delete_cache:
            src.cache.wipe()
    if META.exists():
        META.unlink()
    for k in list(st.session_state):
        del st.session_state[k]
