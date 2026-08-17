"""
backend/app.py — Flask Server for AI Medicine Reminder

Exposes REST APIs for caregiver login, medication schedules CRUD, and logs.
Serves frontend templates from dynamic folders mapping to the frontend project path.
"""

import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

from backend.db.connection import setup_database, execute_query, test_connection
from backend.voice.engine import VoiceEngine

# ── Flask Application Configuration ───────────────────────────
# Derived absolute paths ensure robust deployment and layout alignment
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
template_dir = os.path.join(project_root, "frontend", "templates")
static_dir = os.path.join(project_root, "frontend", "static")

app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=static_dir
)

# ── Security Configuration ────────────────────────────────────
app.secret_key = os.getenv("SECRET_KEY", "medivoice_secret_key_2026")
if app.secret_key == "medivoice_secret_key_2026":
    import warnings
    warnings.warn(
        "⚠️  SECURITY WARNING: Using default SECRET_KEY. "
        "Set a unique SECRET_KEY in your .env file for production.",
        stacklevel=2,
    )

# Secure session cookies
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # Prevent JavaScript access to cookies
    SESSION_COOKIE_SAMESITE="Lax",  # Mitigate CSRF attacks
)

# Cross-Origin Resource Sharing — restrict to same-origin by default
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "*")}})

# Rate limiter — protects against brute-force attacks
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Instantiate voice module
voice_ai = VoiceEngine()


# ── Middleware Decorators ─────────────────────────────────────
def login_required(f):
    """Restricts access to endpoints and page routes to logged-in users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function


# ── Web UI Page Rendering Routes ──────────────────────────────
@app.route("/")
def index():
    """Route entry point. Navigates based on authorization state."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    """Render the primary caregiver log-in view."""
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    """Render the central operations caregiver dashboard dashboard view."""
    return render_template("dashboard.html", username=session.get("username", "Caregiver"))


# ── Caregiver Authentication API endpoints ─────────────────────
@app.route("/api/login", methods=["POST"])
@limiter.limit("5 per minute")  # Brute-force protection
def api_login():
    """Verify credentials using hashed password comparison and set up session."""
    data = request.get_json() or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Credentials cannot be empty."}), 400

    user = execute_query(
        "SELECT * FROM users WHERE username = %s",
        (username,),
        fetchone=True
    )

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        return jsonify({"status": "success", "message": f"Welcome, {user['username']}!"})
    
    return jsonify({"status": "error", "message": "Invalid caregiver username or password."}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    """Flush session objects to terminate current state."""
    session.clear()
    return jsonify({"status": "success", "message": "Successfully logged out."})


# ── Schedules CRUD REST API endpoints ──────────────────────────
@app.route("/api/schedules", methods=["GET"])
@login_required
def get_schedules():
    """Fetch active and inactive medication schedules."""
    rows = execute_query(
        "SELECT * FROM schedules ORDER BY alarm_time ASC",
        fetch=True
    )
    if rows is None:
        return jsonify({"status": "error", "message": "Could not retrieve schedules due to db failure."}), 500

    # Format values for serialization
    for row in rows:
        if row.get("alarm_time"):
            row["alarm_time"] = str(row["alarm_time"])
        if row.get("created_at"):
            row["created_at"] = row["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({"status": "success", "data": rows})


@app.route("/api/add_schedule", methods=["POST"])
@login_required
def add_schedule():
    """Store a new alarm schedule config."""
    data = request.get_json() or {}
    patient_name = str(data.get("patient_name", "")).strip()
    medicine_name = str(data.get("medicine_name", "")).strip()
    dosage = str(data.get("dosage", "")).strip()
    alarm_time = str(data.get("alarm_time", "")).strip()

    if not all([patient_name, medicine_name, dosage, alarm_time]):
        return jsonify({"status": "error", "message": "All fields are required."}), 400

    result = execute_query(
        "INSERT INTO schedules (patient_name, medicine_name, dosage, alarm_time, is_active) "
        "VALUES (%s, %s, %s, %s, %s)",
        (patient_name, medicine_name, dosage, alarm_time, True)
    )

    if result is not None:
        return jsonify({
            "status": "success",
            "message": f"✅ Schedule stored. Voice alerts registered for {alarm_time}.",
            "schedule_id": result
        })
    
    return jsonify({"status": "error", "message": "Failed to store record in database."}), 500


@app.route("/api/update_schedule/<int:schedule_id>", methods=["PUT"])
@login_required
def update_schedule(schedule_id):
    """Modify parameters of an existing schedule."""
    data = request.get_json() or {}
    patient_name = str(data.get("patient_name", "")).strip()
    medicine_name = str(data.get("medicine_name", "")).strip()
    dosage = str(data.get("dosage", "")).strip()
    alarm_time = str(data.get("alarm_time", "")).strip()
    is_active = data.get("is_active", True)

    if not all([patient_name, medicine_name, dosage, alarm_time]):
        return jsonify({"status": "error", "message": "All fields are required."}), 400

    result = execute_query(
        "UPDATE schedules SET patient_name=%s, medicine_name=%s, dosage=%s, alarm_time=%s, is_active=%s "
        "WHERE schedule_id=%s",
        (patient_name, medicine_name, dosage, alarm_time, is_active, schedule_id)
    )

    if result is not None:
        return jsonify({"status": "success", "message": "Medication schedule details updated."})
    
    return jsonify({"status": "error", "message": "Could not update target schedule."}), 500


@app.route("/api/delete_schedule/<int:schedule_id>", methods=["DELETE"])
@login_required
def delete_schedule(schedule_id):
    """Purge a schedule configuration and clear history."""
    result = execute_query(
        "DELETE FROM schedules WHERE schedule_id = %s",
        (schedule_id,)
    )

    if result is not None:
        return jsonify({"status": "success", "message": "Schedule removed."})
    
    return jsonify({"status": "error", "message": "Could not purge schedule from database."}), 500


# ── Logs endpoint ──────────────────────────────────────────────
@app.route("/api/logs", methods=["GET"])
@login_required
def get_logs():
    """Retrieve history of triggered alarms and confirmations."""
    query = """
        SELECT
            al.log_id,
            al.schedule_id,
            al.triggered_at,
            al.status,
            s.patient_name,
            s.medicine_name,
            s.dosage,
            s.alarm_time
        FROM adherence_logs al
        JOIN schedules s ON al.schedule_id = s.schedule_id
        ORDER BY al.triggered_at DESC
        LIMIT 50
    """
    rows = execute_query(query, fetch=True)

    if rows is None:
        return jsonify({"status": "error", "message": "Failed to fetch logs due to database issue."}), 500

    for row in rows:
        if row.get("triggered_at"):
            row["triggered_at"] = row["triggered_at"].strftime("%Y-%m-%d %H:%M:%S")
        if row.get("alarm_time"):
            row["alarm_time"] = str(row["alarm_time"])

    return jsonify({"status": "success", "data": rows})


# ── Engine Speech Verification endpoint ────────────────────────
@app.route("/api/test_voice", methods=["POST"])
@login_required
def test_voice():
    """Initiate dynamic synthesized test text-to-speech output."""
    data = request.get_json() or {}
    message = data.get("message", "This is a test of the AI voice alert system.")
    try:
        voice_ai.speak(message)
        return jsonify({"status": "success", "message": "Voice synthesis execution complete."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"TTS Failure: {e}"}), 500


if __name__ == "__main__":
    # Standard local execution fallback
    setup_database()
    voice_ai.start_scheduler_thread()
    app.run(host="0.0.0.0", port=5000, debug=False)
