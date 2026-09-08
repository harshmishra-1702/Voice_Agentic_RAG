from fastapi.testclient import TestClient
from agent.token_server import app

client = TestClient(app)

def test_experiment_api():
    response = client.post(
        "/api/v1/experiment/memory/run",
        json={
            "sequence": ["A", "B", "C"],
            "memory_size": 4,
            "update_strength": 0.5,
            "interference": 0.1,
            "seed": 42
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "experiment_id" in data
    assert len(data["steps"]) == 3
    assert data["parameters"]["memory_size"] == 4
