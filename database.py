from sqlalchemy import create_engine, text, inspect, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./med_reminder.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce SQLite foreign key constraints so cascades strictly delete all child records."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations():
    """
    Auto-add missing columns to existing tables (lightweight migration).
    Handles upgrades from older schema versions gracefully.
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    # Migrate 'caregivers' table
    if "caregivers" in table_names:
        existing_cols = [col["name"] for col in inspector.get_columns("caregivers")]
        migrations = {
            "caregiver_name": "VARCHAR DEFAULT 'Caregiver'",
            "caregiver_phone": "VARCHAR DEFAULT ''",
            "caregiver_whatsapp": "VARCHAR",
            "patient_name": "VARCHAR DEFAULT 'Friend'",
            "passcode": "VARCHAR",
            "email": "VARCHAR",
            "is_premium": "BOOLEAN DEFAULT 0",
            "premium_expires_at": "DATETIME",
            "consent_accepted": "BOOLEAN DEFAULT 0",
            "created_at": "DATETIME",
        }
        with engine.begin() as conn:
            for col_name, col_type in migrations.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE caregivers ADD COLUMN {col_name} {col_type}"))

    # Migrate 'schedules' table
    if "schedules" in table_names:
        existing_cols = [col["name"] for col in inspector.get_columns("schedules")]
        schedule_migrations = {
            "food_instruction": "VARCHAR DEFAULT 'Any Time'",
            "quantity": "VARCHAR DEFAULT '1 Tablet'",
            "caregiver_id": "INTEGER",
            "bottle_image_url": "VARCHAR",
        }
        with engine.begin() as conn:
            for col_name, col_type in schedule_migrations.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE schedules ADD COLUMN {col_name} {col_type}"))

    # Migrate 'adherence_logs' table
    if "adherence_logs" in table_names:
        existing_cols = [col["name"] for col in inspector.get_columns("adherence_logs")]
        log_migrations = {
            "acknowledged_by_caregiver": "BOOLEAN DEFAULT 0",
        }
        with engine.begin() as conn:
            for col_name, col_type in log_migrations.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE adherence_logs ADD COLUMN {col_name} {col_type}"))
