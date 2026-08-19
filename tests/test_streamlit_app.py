import importlib


def test_streamlit_module_renders(monkeypatch):
    monkeypatch.setenv("APP_MODE", "local")
    module = importlib.import_module("streamlit_app")
    assert callable(module.render_app)
