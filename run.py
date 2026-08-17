"""
run.py — Production Entry Point for AI Medicine Reminder

Responsible for loading environmental variables, executing database checks/seeding,
launching the background daemon voice scheduler, and starting the Flask web server.
"""

import os
from dotenv import load_dotenv

# Ensure environmental variables are loaded at the absolute beginning
load_dotenv()

from backend.db.connection import setup_database, test_connection
from backend.app import app, voice_ai

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Bootstrapping AI Medicine Reminder Application...")
    print("=" * 60)

    # Step 1: Run schema setup and data seeding
    setup_database()

    # Step 2: Diagnostic checks on db connection
    connected, version = test_connection()
    if connected:
        print(f"✅ Database check passed: Connected to MySQL version {version}")
    else:
        print("⚠️  WARNING: Unable to connect to MySQL database.")
        print("   Please check your credentials in the local .env configuration.")
        print("   Web dashboard will load, but scheduling will remain inactive.\n")

    # Step 3: Launch daemon Voice AI background scheduler
    print("🧠 Initializing voice engine scheduler...")
    voice_ai.start_scheduler_thread()

    # Step 4: Run Flask web server
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))
    print(f"\n🌐 Web interface listening on http://localhost:{port}")
    app.run(host=host, port=port, debug=False)
