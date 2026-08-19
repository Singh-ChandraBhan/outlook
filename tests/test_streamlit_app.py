from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_module_renders(monkeypatch):
    monkeypatch.setenv("APP_MODE", "local")
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(app_path, default_timeout=30).run()
    assert not app.exception
    assert not app.error
