# 🧠 AI Medicine Reminder

An intelligent medication reminder system powered by **Flask**, **MySQL**, and **AI Voice Synthesis**. It delivers timely spoken alerts for scheduled medications and listens for patient voice confirmation, logging adherence automatically.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔔 **Scheduled Voice Alerts** | Automatic text-to-speech reminders at configured medication times |
| 🎤 **Voice Confirmation** | Listens for patient verbal confirmation ("taken", "done", "yes") |
| 📊 **Caregiver Dashboard** | Web-based UI to manage schedules, view logs, and monitor adherence |
| 🔐 **Secure Authentication** | Password hashing (Werkzeug), rate-limited login, CORS protection |
| 📝 **Adherence Logging** | Automatic logging of taken/missed doses with timestamps |

---

## 🏗️ Project Structure

```
AI-med-remainder/
├── backend/
│   ├── __init__.py
│   ├── app.py                 # Flask server, REST APIs, security middleware
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py      # MySQL connection pool, schema setup, seeding
│   │   └── schema.sql         # Database table definitions
│   └── voice/
│       ├── __init__.py
│       └── engine.py          # TTS synthesis, speech recognition, scheduler
├── frontend/
│   ├── templates/
│   │   ├── login.html         # Caregiver login page
│   │   └── dashboard.html     # Main operations dashboard
│   └── static/
│       ├── css/               # Stylesheets
│       └── js/                # Client-side scripts
├── .env.example               # Environment variable template
├── .gitignore                 # Git exclusion rules
├── requirements.txt           # Python dependencies
├── run.py                     # Application entry point
└── README.md                  # This file
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- **MySQL Server** (5.7+ or 8.x)
- **Microphone** (for voice confirmation features)
- **Speakers/Audio Output** (for TTS alerts)

### 1. Clone the Repository

```bash
git clone https://github.com/Sureshkrishna17/AI-med-remainder.git
cd AI-med-remainder
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv

# Activate on Windows
.venv\Scripts\activate

# Activate on macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the example and fill in your actual values
cp .env.example .env
```

Edit `.env` with your MySQL credentials and a secure secret key:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_actual_password
DB_NAME=medicine_db
SECRET_KEY=your_random_secret_key_here
```

> 💡 **Tip:** Generate a strong SECRET_KEY with:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 5. Run the Application

```bash
python run.py
```

The application will:
1. ✅ Create the database and tables automatically
2. ✅ Seed a default admin account (first run only)
3. ✅ Start the background voice scheduler
4. ✅ Launch the web dashboard at `http://localhost:5000`

---

## 🔐 Security Features

| Feature | Implementation |
|---|---|
| **Password Hashing** | Werkzeug `pbkdf2:sha256` — no plaintext passwords stored |
| **Rate Limiting** | Flask-Limiter: 5 login attempts/minute, 200 requests/day |
| **CORS Protection** | Flask-CORS with configurable origin whitelist |
| **Secure Sessions** | HTTPOnly cookies, SameSite=Lax policy |
| **Environment Isolation** | Sensitive config via `.env` (excluded from Git) |

---

## 📡 API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/login` | ❌ | Authenticate caregiver (rate-limited) |
| `POST` | `/api/logout` | ❌ | End current session |
| `GET` | `/api/schedules` | ✅ | List all medication schedules |
| `POST` | `/api/add_schedule` | ✅ | Create a new schedule |
| `PUT` | `/api/update_schedule/<id>` | ✅ | Update an existing schedule |
| `DELETE` | `/api/delete_schedule/<id>` | ✅ | Remove a schedule |
| `GET` | `/api/logs` | ✅ | View adherence logs (last 50) |
| `POST` | `/api/test_voice` | ✅ | Test the TTS voice engine |

---

## 🔧 Default Credentials

| Field | Value |
|---|---|
| Username | `admin` |
| Password | Set in `.env` as `ADMIN_PASSWORD` |

> ⚠️ **Change the default `ADMIN_PASSWORD` in your `.env` before deploying to production.**

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 👤 Author

Built with ❤️ as an AI-powered healthcare assistant project.
