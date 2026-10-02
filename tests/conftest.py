import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path}/business.sqlite",
                    checkpoint_file=str(tmp_path / "checkpoints.sqlite"),
                    api_key="test-api-key-long-enough-for-tests")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        c.headers["X-API-Key"] = settings.api_key
        yield c


def investigate(client, ticket="TKT-1001"):
    response = client.post(f"/api/tickets/{ticket}/investigate")
    assert response.status_code == 200, response.text
    return response.json()


def decide(client, run, action="approve"):
    return client.post(f"/api/runs/{run['id']}/decision", json={"action": action, "reviewer": "Demo reviewer", "note": "Evidence checked"})
