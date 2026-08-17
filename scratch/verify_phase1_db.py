import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, SessionLocal, Base
from models import User, Schedule, AdherenceLog

def test_db_models():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

    db = SessionLocal()
    try:
        # Create a test user
        test_user = User(
            patient_phone="+15550101",
            caregiver_phone="+15550102",
            language="en"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"Created User: ID={test_user.id}, Patient={test_user.patient_phone}")

        # Create a test schedule
        test_sched = Schedule(
            user_id=test_user.id,
            med_name="Aspirin",
            time_str="08:00",
            tactile_marker="Rubber Band",
            is_active=True
        )
        db.add(test_sched)
        db.commit()
        db.refresh(test_sched)
        print(f"Created Schedule: ID={test_sched.id}, Med={test_sched.med_name}, Marker={test_sched.tactile_marker}")

        # Create a test log
        test_log = AdherenceLog(
            schedule_id=test_sched.id,
            status="Pending",
            retry_count=0
        )
        db.add(test_log)
        db.commit()
        db.refresh(test_log)
        print(f"Created AdherenceLog: ID={test_log.id}, Status={test_log.status}")

        print("Verification successful!")
    finally:
        db.close()

if __name__ == "__main__":
    test_db_models()
