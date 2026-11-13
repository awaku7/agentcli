from __future__ import annotations

from fastapi.testclient import TestClient

from uagent.web_impl.app import app


def test_static_mjs_module_is_served_with_javascript_mime_type() -> None:
    response = TestClient(app).get("/static/command-picker.mjs")

    assert response.status_code == 200
    assert response.headers["content-type"].split(";", 1)[0] in {
        "application/javascript",
        "text/javascript",
    }
