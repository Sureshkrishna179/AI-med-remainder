"""
backend/db/connection.py — Database Connection Manager for AI Medicine Reminder

Maintains a connection pool for MySQL queries and manages initial database setup.
Loads environment configuration values from .env.
"""

import os
import mysql.connector
from mysql.connector import pooling, Error
from werkzeug.security import generate_password_hash

# Load environment configuration variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "medicine_db")

# Admin account seeding configuration
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Connection pool holder
_connection_pool = None


def _create_pool(database=None):
    """Create a MySQL connection pool using loaded configuration."""
    config = {
        "host": DB_HOST,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    if database:
        config["database"] = database

    try:
        return pooling.MySQLConnectionPool(
            pool_name="medicine_pool",
            pool_size=5,
            pool_reset_session=True,
            **config,
        )
    except Error as e:
        print(f"❌ Error creating MySQL connection pool: {e}")
        return None


def get_connection():
    """Retrieve a connection from the pool, initializing the pool if needed."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = _create_pool(database=DB_NAME)

    if _connection_pool:
        try:
            return _connection_pool.get_connection()
        except Error as e:
            print(f"❌ Error retrieving connection from pool: {e}")
            return None
    return None


def execute_query(query, params=None, fetch=False, fetchone=False):
    """Execute a database query, supporting parameterization and fetch operations."""
    conn = get_connection()
    if conn is None:
        return None

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())

        if fetch:
            return cursor.fetchall()
        elif fetchone:
            return cursor.fetchone()
        else:
            conn.commit()
            return cursor.lastrowid
    except Error as e:
        print(f"❌ Query execution error: {e}")
        if not fetch and not fetchone:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def setup_database():
    """Initialize the schema, seed the default admin and sample data if needed."""
    print("🔧 Configuring database...")

    # Step 1: Connect to server without database specification to create it if missing
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")
        print(f"✅ Database '{DB_NAME}' established successfully.")

        # Step 2: Read and execute tables definition from schema.sql
        current_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(current_dir, "schema.sql")

        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            # Split statements by semicolon and run each non-empty query
            statements = schema_sql.split(";")
            for statement in statements:
                clean_statement = statement.strip()
                if clean_statement:
                    cursor.execute(clean_statement)
            print("✅ Database tables established successfully from schema.sql.")
        else:
            print("⚠️ WARNING: schema.sql file not found. Skipping table generation.")

        # Step 3: Seed primary admin user if users table is empty
        cursor.execute("SELECT COUNT(*) AS cnt FROM users")
        if cursor.fetchone()[0] == 0:
            hashed_password = generate_password_hash(ADMIN_PASSWORD)
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (ADMIN_USER, hashed_password, "Caregiver")
            )
            print(f"✅ Default caregiver account created (Username: {ADMIN_USER}).")

        # Step 4: Seed demo schedules if table is empty
        cursor.execute("SELECT COUNT(*) AS cnt FROM schedules")
        if cursor.fetchone()[0] == 0:
            sample_data = [
                ("Grandpa", "Paracetamol", "1 Tablet", "08:00:00", True),
                ("Grandma", "Vitamin D",   "10 ml",    "13:00:00", True),
                ("Grandpa", "Aspirin",     "1 Tablet", "20:00:00", True),
            ]
            cursor.executemany(
                "INSERT INTO schedules (patient_name, medicine_name, dosage, alarm_time, is_active) "
                "VALUES (%s, %s, %s, %s, %s)",
                sample_data
            )
            print("✅ Sample schedules seeded.")

        conn.commit()
        print("🎉 Database setup process completed successfully!")
        return True

    except Error as e:
        print(f"❌ Database setup failed: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def test_connection():
    """Verify connectivity to the MySQL database."""
    conn = get_connection()
    if conn and conn.is_connected():
        server_info = conn.get_server_info()
        conn.close()
        return True, server_info
    return False, None


if __name__ == "__main__":
    setup_database()
