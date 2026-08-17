import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app, check_due_schedules, SessionLocal
import models
from telephony import trigger_voice_call, send_caregiver_sms

client = TestClient(app)

def test_telephony_and_escalation():
    print("--- Testing Phase 3: Telephony & IVR Callbacks ---")
    
    # Create user & schedule directly in DB
    db = SessionLocal()
    try:
        user = models.User(patient_phone="+15550199", caregiver_phone="+15550299", language="en")
        db.add(user)
        db.commit()

        sched = models.Schedule(
            user_id=user.id,
            med_name="Blood Pressure Med",
            time_str="09:00",
            tactile_marker="Rough Tape",
            is_active=True
        )
        db.add(sched)
        db.commit()

        log = models.AdherenceLog(
            schedule_id=sched.id,
            timestamp=datetime.utcnow(),
            status="Pending",
            retry_count=0
        )
        db.add(log)
        db.commit()
        log_id = log.id

        # 1. Test voice call trigger safety function
        call_success = trigger_voice_call(user.patient_phone, sched.tactile_marker, log_id)
        print(f"trigger_voice_call executed safely (success={call_success})")

        # 2. Test POST /voice-callback/{log_id}
        res_voice = client.post(f"/voice-callback/{log_id}")
        print(f"POST /voice-callback/{log_id} status: {res_voice.status_code}")
        print(f"TwiML Content:\n{res_voice.text}")
        assert res_voice.status_code == 200
        assert "Please open the container with the Rough Tape" in res_voice.text
        assert "gather-callback" in res_voice.text

        # 3. Test POST /gather-callback/{log_id} with Digits="1"
        res_gather = client.post(f"/gather-callback/{log_id}", data={"Digits": "1"})
        print(f"POST /gather-callback/{log_id} (Digits=1) status: {res_gather.status_code}")
        assert res_gather.status_code == 200
        assert "confirmed" in res_gather.text.lower()

        # Verify DB log status updated to "Confirmed"
        db.refresh(log)
        assert log.status == "Confirmed"
        print(f"Verified AdherenceLog #{log_id} status in DB: {log.status}")

        print("\n--- Testing Phase 4: Escalation Engine ---")

        # Create a stale pending log (>15 mins old)
        stale_log = models.AdherenceLog(
            schedule_id=sched.id,
            timestamp=datetime.utcnow() - timedelta(minutes=20),
            status="Pending",
            retry_count=0
        )
        db.add(stale_log)
        db.commit()
        stale_id = stale_log.id

        # Run scheduler check job to trigger Retry #1
        check_due_schedules()

        db.refresh(stale_log)
        print(f"Stale Log #{stale_id} after Escalation 1: retry_count={stale_log.retry_count}, status={stale_log.status}")
        assert stale_log.retry_count == 1
        assert stale_log.status == "Pending"

        # Set timestamp back 20 minutes to trigger Escalation 2 (Missed + SMS)
        stale_log.timestamp = datetime.utcnow() - timedelta(minutes=20)
        db.commit()

        check_due_schedules()

        db.refresh(stale_log)
        print(f"Stale Log #{stale_id} after Escalation 2: retry_count={stale_log.retry_count}, status={stale_log.status}")
        assert stale_log.status == "Missed"

        print("\nPhase 3 & 4 tests passed successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    test_telephony_and_escalation()
