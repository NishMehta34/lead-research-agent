import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # needed by FastAPI's TestClient

from fastapi.testclient import TestClient  # noqa: E402

import app.agent  # noqa: E402
import app.api as api  # noqa: E402
from tests.conftest import FakeLLM, fake_fetch  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "get_llm", FakeLLM)
    # route all page fetches to the fake website
    original = app.agent.research_company
    monkeypatch.setattr(api, "research_company",
                        lambda url, llm: original(url, llm, fetch=fake_fetch))
    return TestClient(api.app)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_research_endpoint(client):
    response = client.post("/research", json={"url": "acme.test"})
    assert response.status_code == 200
    assert response.json()["profile"]["name"] == "Acme Logistics"


def test_markdown_endpoint(client):
    response = client.post("/research/markdown", json={"url": "acme.test"})
    assert response.text.startswith("# Lead brief: Acme Logistics")
