import sys
import os
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app, check_due_schedules, get_db, SessionLocal
import models

client = TestClient(app)

def test_phase2_endpoints_and_scheduler():
    print("--- Testing Phase 2 FastAPI REST Endpoints ---")
    
    # 1. Create User
    user_payload = {
        "patient_phone": "+12345678901",
        "caregiver_phone": "+19876543210",
        "language": "en"
    }
    res = client.post("/users/", json=user_payload)
    print(f"POST /users/ status: {res.status_code}, body: {res.json()}")
    assert res.status_code == 201
    user_id = res.json()["id"]

    # Current time format HH:MM
    current_time_str = datetime.now().strftime("%H:%M")

    # 2. Create Schedule with current time
    schedule_payload = {
        "user_id": user_id,
        "med_name": "Aspirin 81mg",
        "time_str": current_time_str,
        "tactile_marker": "Rubber Band",
        "is_active": True
    }
    res = client.post("/schedules/", json=schedule_payload)
    print(f"POST /schedules/ status: {res.status_code}, body: {res.json()}")
    assert res.status_code == 201
    sched_id = res.json()["id"]

    # 3. GET /schedules/{user_id}
    res = client.get(f"/schedules/{user_id}")
    print(f"GET /schedules/{user_id} status: {res.status_code}, body: {res.json()}")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 4. Execute check_due_schedules() directly to simulate background scheduler trigger
    print("\n--- Triggering check_due_schedules() ---")
    check_due_schedules()

    # 5. GET /logs/{user_id}
    res = client.get(f"/logs/{user_id}")
    print(f"GET /logs/{user_id} status: {res.status_code}, body: {res.json()}")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    assert logs[0]["status"] == "Pending"
    assert logs[0]["tactile_marker"] == "Rubber Band"

    print("\nPhase 2 test completed successfully!")

if __name__ == "__main__":
    test_phase2_endpoints_and_scheduler()
