import pytest
from skeleton_key.config import HostConfig
from skeleton_key.ui.app import create_app


@pytest.fixture
def test_client():
    app = create_app(config=HostConfig(project_roots=[]))
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_route(test_client):
    res = test_client.get("/")
    assert res.status_code == 200
    assert b"Skeleton Key" in res.data
    assert b"AirDrop-style" in res.data


def test_profile_api(test_client):
    res = test_client.get("/api/profile")
    assert res.status_code == 200
    data = res.get_json()
    assert "os" in data
    assert "arch" in data
    assert "home" in data


def test_state_api(test_client):
    res = test_client.get("/api/state")
    assert res.status_code == 200
    data = res.get_json()
    assert "local_profile" in data
    assert "host" in data
    assert "client" in data


def test_host_manifest_api(test_client):
    res = test_client.get("/api/host/manifest")
    assert res.status_code == 200
    data = res.get_json()
    assert "items" in data
    assert "projects" in data
