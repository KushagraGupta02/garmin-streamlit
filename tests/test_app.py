"""Render every page in demo mode and fail on any exception."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted(p.stem for p in (ROOT / "views").glob("*.py"))


def _demo_app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    next(b for b in at.button if b.label == "Open demo").click().run()
    assert not at.exception, at.exception
    return at


def test_login_page_renders():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert any("Privacy" in h.value for h in at.subheader)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = _demo_app()
    at.switch_page(f"views/{page}.py").run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
