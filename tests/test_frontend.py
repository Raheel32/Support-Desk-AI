from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

FRONTEND = str(Path(__file__).resolve().parents[1] / "frontend" / "streamlit_app.py")


def test_login_overview_investigate_approve_and_history(client, monkeypatch, settings):
    monkeypatch.setenv("APP_PASSWORD", "workspace-test-password")
    monkeypatch.setenv("BACKEND_API_KEY", settings.api_key)
    monkeypatch.setenv("API_BASE_URL", "http://testserver")

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    with patch("httpx.request", side_effect=request):
        app = AppTest.from_file(FRONTEND, default_timeout=30).run()
        assert not app.exception
        app.text_input[0].set_value("workspace-test-password")
        next(b for b in app.button if b.label == "Open workspace").click().run()
        assert not app.exception
        assert len(app.metric) == 4
        app.radio[0].set_value("Ticket workspace").run()
        assert not app.exception
        next(b for b in app.button if b.label == "Investigate ticket").click().run()
        assert not app.exception
        assert any(b.label == "Approve simulated refund" for b in app.button)
        next(t for t in app.text_input if t.label == "Reviewer name").set_value("Demo reviewer")
        app.checkbox[0].check()
        next(b for b in app.button if b.label == "Approve simulated refund").click().run()
        assert not app.exception
        assert any("Simulated refund completed" in s.value for s in app.success)
        app.radio[0].set_value("Create ticket").run()
        assert not app.exception
        next(t for t in app.text_input if t.label == "Subject").set_value("A new support question")
        next(t for t in app.text_area if t.label == "What happened?").set_value("Please check the transaction for this fictional order.")
        next(b for b in app.button if b.label == "Create ticket").click().run()
        assert not app.exception
        assert any("Created TKT-" in s.value for s in app.success)
        app.radio[0].set_value("How it works").run()
        assert not app.exception
