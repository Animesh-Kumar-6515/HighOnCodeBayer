import json
from pathlib import Path

BASE_PATH = Path("mock-data")

def load_json(path: Path):
    with open(path, "r") as f:
        return json.load(f)

def load_all_mock_data(incident_id: str):
    return {
        "topology": load_json(BASE_PATH / "topology/production.json"),
        "scenario": load_json(
            BASE_PATH / f"scenarios/{incident_id}-database-failure.json"
        ),
        "logs": {
            "high_level": load_json(BASE_PATH / f"logs/{incident_id}/high_level.json"),
            "application": load_json(BASE_PATH / f"logs/{incident_id}/application_logs.json"),
            "database": load_json(BASE_PATH / f"logs/{incident_id}/database_logs.json"),
            "infrastructure": load_json(
                BASE_PATH / f"logs/{incident_id}/infrastructure_logs.json"
            ),
        },
        "metrics": {
            "application": load_json(
                BASE_PATH / f"metrics/{incident_id}/application_metrics.json"
            ),
            "database": load_json(
                BASE_PATH / f"metrics/{incident_id}/database_metrics.json"
            ),
            "infrastructure": load_json(
                BASE_PATH / f"metrics/{incident_id}/infrastructure_metrics.json"
            ),
        }
    }
