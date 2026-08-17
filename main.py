import os
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Form, Response, Request, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv

load_dotenv()

from database import engine, SessionLocal, Base, get_db, run_migrations
import models
import schemas
from telephony import trigger_voice_call, send_caregiver_sms

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("med_reminder")

# Create database tables & run migrations for existing DBs
Base.metadata.create_all(bind=engine)
run_migrations()

# Razorpay config
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

# Initialize background scheduler
scheduler = BackgroundScheduler()

def check_due_schedules():
    """
    Background job running every 60 seconds.
    1. Triggers pending logs for schedules matching current system time (HH:MM).
    2. Escalation engine: Escalates pending logs older than 15 minutes.
       - retry_count == 0: Retry call to patient & increment retry_count to 1.
       - retry_count == 1: Mark status as 'Missed' & send SMS to caregiver.
    """
    now = datetime.utcnow()
    current_hh_mm = datetime.now().strftime("%H:%M")
    
    db: Session = SessionLocal()
    try:
        # Step 1: Check due schedules
        due_schedules = db.query(models.Schedule).filter(
            models.Schedule.is_active == True,
            models.Schedule.time_str == current_hh_mm
        ).all()

        for schedule in due_schedules:
            start_of_minute = now.replace(second=0, microsecond=0)
            existing_log = db.query(models.AdherenceLog).filter(
                models.AdherenceLog.schedule_id == schedule.id,
                models.AdherenceLog.timestamp >= start_of_minute
            ).first()

            if not existing_log:
                new_log = models.AdherenceLog(
                    schedule_id=schedule.id,
                    timestamp=now,
                    status="Pending",
                    retry_count=0
                )
                db.add(new_log)
                db.commit()
                db.refresh(new_log)
                logger.info(f"Triggered schedule for {schedule.tactile_marker} container at {current_hh_mm} (Med: {schedule.med_name})")

                # Initiate initial voice call to patient
                caregiver = schedule.caregiver
                patient_phone = caregiver.patient_phone if caregiver else None
                if patient_phone:
                    trigger_voice_call(patient_phone, schedule.tactile_marker, new_log.id)

        # Step 2: Escalation engine for pending logs > 15 minutes
        cutoff_time = now - timedelta(minutes=15)
        stale_pending_logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.status == "Pending",
            models.AdherenceLog.timestamp <= cutoff_time
        ).all()

        for log in stale_pending_logs:
            schedule = log.schedule
            if not schedule or not schedule.caregiver:
                continue

            patient_phone = schedule.caregiver.patient_phone
            caregiver_phone = schedule.caregiver.caregiver_phone
            tactile_marker = schedule.tactile_marker

            if log.retry_count == 0:
                # Retry call to patient
                log.retry_count = 1
                log.timestamp = now  # Reset window for second retry
                db.commit()
                logger.info(f"Escalation: Retry call #1 for log #{log.id} to patient {patient_phone}")
                trigger_voice_call(patient_phone, tactile_marker, log.id)

            elif log.retry_count == 1:
                # Mark as Missed and alert Caregiver via SMS
                log.status = "Missed"
                db.commit()
                user_lang = schedule.caregiver.language if schedule.caregiver else "en"
                patient_name = schedule.caregiver.patient_name if schedule.caregiver else "Friend"
                logger.info(f"Escalation: Marking log #{log.id} as Missed. Sending SMS to caregiver {caregiver_phone} (lang={user_lang})")
                send_caregiver_sms(caregiver_phone, tactile_marker, patient_name=patient_name, language=user_lang)

    except Exception as e:
        logger.error(f"Error in check_due_schedules background job: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting background scheduler...")
    scheduler.add_job(check_due_schedules, "interval", seconds=60, id="check_due_schedules")
    scheduler.start()
    yield
    logger.info("Shutting down background scheduler...")
    scheduler.shutdown()

app = FastAPI(
    title="MedAssist AI — Medication Reminder System",
    description="Voice-based medication adherence system with caregiver dashboard, Twilio IVR, and Razorpay subscriptions.",
    lifespan=lifespan
)

# Serve static dashboard files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_dashboard():
    """Serves the Caregiver Dashboard UI."""
    return FileResponse("static/index.html")


# ==========================================
# CAREGIVER API
# ==========================================

@app.post("/caregivers/", response_model=schemas.CaregiverResponse, status_code=status.HTTP_201_CREATED)
def create_caregiver(data: schemas.CaregiverCreate, db: Session = Depends(get_db)):
    """Register a new caregiver with patient info."""
    # Check if phone already exists
    existing = db.query(models.Caregiver).filter(
        models.Caregiver.caregiver_phone == data.caregiver_phone
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This phone number is already registered. Please log in instead.")

    db_caregiver = models.Caregiver(
        caregiver_name=data.caregiver_name,
        caregiver_phone=data.caregiver_phone,
        caregiver_whatsapp=data.caregiver_whatsapp,
        passcode=data.passcode,
        patient_name=data.patient_name,
        patient_phone=data.patient_phone,
        language=data.language or "en",
        consent_accepted=data.consent_accepted,
    )
    db.add(db_caregiver)
    db.commit()
    db.refresh(db_caregiver)
    return db_caregiver


@app.post("/caregivers/login", response_model=schemas.CaregiverResponse)
def login_caregiver(data: schemas.CaregiverLogin, db: Session = Depends(get_db)):
    """Authenticate caregiver with phone + passcode."""
    caregiver = db.query(models.Caregiver).filter(
        models.Caregiver.caregiver_phone == data.caregiver_phone
    ).first()

    if not caregiver or caregiver.passcode != data.passcode:
        raise HTTPException(status_code=401, detail="Invalid phone number or passcode.")

    # Check premium expiry
    if caregiver.is_premium and caregiver.premium_expires_at:
        if caregiver.premium_expires_at < datetime.utcnow():
            caregiver.is_premium = False
            db.commit()

    return caregiver


@app.get("/caregivers/{caregiver_id}", response_model=schemas.CaregiverResponse)
def get_caregiver(caregiver_id: int, db: Session = Depends(get_db)):
    """Get caregiver profile by ID."""
    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == caregiver_id).first()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")
    return caregiver


@app.delete("/caregivers/{caregiver_id}", status_code=status.HTTP_200_OK)
def delete_caregiver(caregiver_id: int, db: Session = Depends(get_db)):
    """
    Permanently delete caregiver account and all associated data without trace.
    Purges: AdherenceLogs → Schedules → Subscriptions → Caregiver
    """
    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == caregiver_id).first()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    # Step 1: Find all schedule IDs owned by caregiver
    schedule_ids = [s.id for s in caregiver.schedules]

    # Step 2: Delete all adherence logs associated with those schedules
    if schedule_ids:
        db.query(models.AdherenceLog).filter(
            models.AdherenceLog.schedule_id.in_(schedule_ids)
        ).delete(synchronize_session=False)

    # Step 3: Delete all schedules
    db.query(models.Schedule).filter(
        models.Schedule.caregiver_id == caregiver_id
    ).delete(synchronize_session=False)

    # Step 4: Delete all subscriptions
    db.query(models.Subscription).filter(
        models.Subscription.caregiver_id == caregiver_id
    ).delete(synchronize_session=False)

    # Step 5: Delete caregiver record
    db.delete(caregiver)
    db.commit()

    logger.info(f"PERMANENT PURGE COMPLETE: Caregiver #{caregiver_id} and all related schedules ({len(schedule_ids)}), logs, and subscriptions completely deleted with zero trace.")
    return {"status": "success", "message": "Account and all associated data permanently deleted without trace."}


# ==========================================
# SCHEDULE API
# ==========================================

@app.post("/schedules/", response_model=schemas.ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(schedule: schemas.ScheduleCreate, db: Session = Depends(get_db)):
    """Add a medication schedule with time, tactile marker, food instructions, and quantity."""
    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == schedule.caregiver_id).first()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    # Free tier: limit to 1 schedule
    if not caregiver.is_premium:
        existing_count = db.query(models.Schedule).filter(
            models.Schedule.caregiver_id == caregiver.id,
            models.Schedule.is_active == True
        ).count()
        if existing_count >= 1:
            raise HTTPException(status_code=403, detail="Free tier allows 1 schedule. Subscribe for unlimited schedules.")

    db_schedule = models.Schedule(
        caregiver_id=schedule.caregiver_id,
        med_name=schedule.med_name,
        time_str=schedule.time_str,
        tactile_marker=schedule.tactile_marker,
        food_instruction=schedule.food_instruction or "Any Time",
        quantity=schedule.quantity or "1 Tablet",
        is_active=schedule.is_active if schedule.is_active is not None else True
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


@app.get("/schedules/{caregiver_id}", response_model=List[schemas.ScheduleResponse])
def get_schedules(caregiver_id: int, db: Session = Depends(get_db)):
    """Retrieve all schedules for a given caregiver."""
    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == caregiver_id).first()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")
    return db.query(models.Schedule).filter(models.Schedule.caregiver_id == caregiver_id).all()


@app.put("/schedules/{schedule_id}", response_model=schemas.ScheduleResponse)
def update_schedule(schedule_id: int, data: schemas.ScheduleUpdate, db: Session = Depends(get_db)):
    """Update an existing medication schedule (edit dosage, time, pause/resume, etc.)."""
    schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)
    logger.info(f"Schedule #{schedule_id} updated: {update_data}")
    return schedule


@app.delete("/schedules/{schedule_id}", status_code=status.HTTP_200_OK)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Permanently delete a schedule and all its adherence logs."""
    schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Delete child logs first
    db.query(models.AdherenceLog).filter(
        models.AdherenceLog.schedule_id == schedule_id
    ).delete(synchronize_session=False)

    db.delete(schedule)
    db.commit()
    logger.info(f"Schedule #{schedule_id} and all associated logs permanently deleted.")
    return {"status": "success", "message": "Schedule and associated logs deleted."}


@app.post("/logs/{log_id}/acknowledge", status_code=status.HTTP_200_OK)
def acknowledge_missed_log(log_id: int, db: Session = Depends(get_db)):
    """Mark a missed-dose log as acknowledged by the caregiver."""
    log = db.query(models.AdherenceLog).filter(models.AdherenceLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Adherence log not found")

    log.acknowledged_by_caregiver = True
    db.commit()
    logger.info(f"Adherence log #{log_id} acknowledged by caregiver.")
    return {"status": "success", "message": "Missed dose acknowledged."}


@app.post("/uploads/bottle-photo")
async def upload_bottle_photo(file: UploadFile = File(...)):
    """Upload a bottle photo (max 5 MB). Returns the URL path for the stored image."""
    import uuid

    # Validate file size (5 MB max)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5 MB.")

    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, WebP, GIF.")

    # Save file
    upload_dir = os.path.join("static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    url_path = f"/static/uploads/{filename}"
    logger.info(f"Bottle photo uploaded: {url_path} ({len(contents)} bytes)")
    return {"url": url_path, "filename": filename}


@app.get("/logs/{caregiver_id}", response_model=List[schemas.AdherenceLogResponse])
def get_logs(caregiver_id: int, db: Session = Depends(get_db)):
    """Retrieve adherence history for a given caregiver's patient."""
    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == caregiver_id).first()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    logs = db.query(models.AdherenceLog).join(models.Schedule).filter(
        models.Schedule.caregiver_id == caregiver_id
    ).order_by(models.AdherenceLog.timestamp.desc()).all()

    result = []
    for log in logs:
        result.append(schemas.AdherenceLogResponse(
            id=log.id,
            schedule_id=log.schedule_id,
            timestamp=log.timestamp,
            status=log.status,
            retry_count=log.retry_count,
            acknowledged_by_caregiver=log.acknowledged_by_caregiver or False,
            med_name=log.schedule.med_name if log.schedule else None,
            tactile_marker=log.schedule.tactile_marker if log.schedule else None,
            food_instruction=log.schedule.food_instruction if log.schedule else None,
            quantity=log.schedule.quantity if log.schedule else None,
        ))
    return result


# ==========================================
# TWILIO VOICE & IVR CALLBACKS
# ==========================================

@app.post("/voice-callback/{log_id}")
async def voice_callback(log_id: int, request: Request, marker: Optional[str] = "designated", db: Session = Depends(get_db)):
    """
    Twilio outbound call webhook endpoint.
    Returns TwiML with <Gather> prompting patient to press 1 to confirm medication.
    Enhanced with food instructions and quantity in the voice script.
    """
    log = db.query(models.AdherenceLog).filter(models.AdherenceLog.id == log_id).first()
    tactile_marker = log.schedule.tactile_marker if (log and log.schedule) else marker

    # Determine language, patient name, and schedule details
    user_lang = "en"
    patient_name = "Friend"
    food_instruction = ""
    quantity = "your medicine"
    if log and log.schedule and log.schedule.caregiver:
        user_lang = log.schedule.caregiver.language or "en"
        patient_name = log.schedule.caregiver.patient_name or "Friend"
        food_instruction = log.schedule.food_instruction or "Any Time"
        quantity = log.schedule.quantity or "your medicine"

    response = VoiceResponse()
    gather = Gather(num_digits=1, action=f"/gather-callback/{log_id}", method="POST")

    # Build food instruction text
    food_text_en = ""
    food_text_ta = ""
    if food_instruction == "Before Food":
        food_text_en = "before your food"
        food_text_ta = "சாப்பிடுவதற்கு முன்"
    elif food_instruction == "After Food":
        food_text_en = "after your food"
        food_text_ta = "சாப்பிட்ட பிறகு"
    elif food_instruction == "With Food":
        food_text_en = "with your food"
        food_text_ta = "சாப்பாட்டுடன்"

    if user_lang == "ta":
        food_part = f" {food_text_ta}" if food_text_ta else ""
        gather.say(
            f"வணக்கம் {patient_name}. உங்கள் மருந்து நேரம் வந்துவிட்டது. "
            f"{tactile_marker} உள்ள பாட்டிலை எடுங்கள். "
            f"{quantity}{food_part} எடுத்துக்கொள்ளுங்கள். "
            f"விழுங்கியதும் 1 ஐ அழுத்தவும்.",
            language="ta-IN"
        )
    else:
        food_part = f" {food_text_en}" if food_text_en else ""
        gather.say(
            f"Hello {patient_name}. It is time for your medication. "
            f"Please pick up the container with the {tactile_marker}. "
            f"Take {quantity}{food_part}. "
            f"Press 1 on your keypad when you have swallowed them.",
            voice="alice"
        )

    response.append(gather)

    # Fallback if no digit pressed
    if user_lang == "ta":
        response.say("பதில் எதுவும் பெறப்படவில்லை. நன்றி.", language="ta-IN")
    else:
        response.say("We did not receive any input. Goodbye.", voice="alice")
    
    return Response(content=str(response), media_type="application/xml")


@app.post("/gather-callback/{log_id}")
async def gather_callback(log_id: int, Digits: Optional[str] = Form(None), db: Session = Depends(get_db)):
    """
    Twilio DTMF keypress callback webhook.
    Parses DTMF input: If Digits == "1", mark status as "Confirmed". Otherwise play error & hang up.
    """
    response = VoiceResponse()
    log = db.query(models.AdherenceLog).filter(models.AdherenceLog.id == log_id).first()

    # Determine language
    user_lang = "en"
    if log and log.schedule and log.schedule.caregiver:
        user_lang = log.schedule.caregiver.language or "en"

    if Digits == "1":
        if log:
            log.status = "Confirmed"
            db.commit()
            logger.info(f"Voice Callback: Log #{log_id} confirmed by patient via DTMF '1'.")
        if user_lang == "ta":
            response.say("நன்றி. உங்கள் மருந்து பதில் உறுதிப்படுத்தப்பட்டது. நன்றி.", language="ta-IN")
        else:
            response.say("Thank you. Your medication response has been confirmed. Goodbye.", voice="alice")
    else:
        logger.warning(f"Voice Callback: Log #{log_id} failed confirmation (Received Digits='{Digits}').")
        if user_lang == "ta":
            response.say("உறுதிப்படுத்தல் தோல்வியடைந்தது.", language="ta-IN")
        else:
            response.say("Confirmation failed.", voice="alice")
        response.hangup()

    return Response(content=str(response), media_type="application/xml")


# ==========================================
# RAZORPAY SUBSCRIPTION API
# ==========================================

@app.post("/subscriptions/create-order")
def create_subscription_order(data: schemas.SubscriptionCreateOrder, db: Session = Depends(get_db)):
    """Create a Razorpay order for ₹199 subscription."""
    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == data.caregiver_id).first()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    amount = 19900  # ₹199 in paise

    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET and not RAZORPAY_KEY_ID.startswith("your_"):
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": f"medassist_sub_{caregiver.id}_{int(datetime.utcnow().timestamp())}",
            "notes": {"caregiver_id": str(caregiver.id)}
        })
        order_id = order["id"]
    else:
        # Mock mode
        order_id = f"order_mock_{int(datetime.utcnow().timestamp())}"
        logger.info(f"[MOCK RAZORPAY] Created order {order_id} for caregiver #{caregiver.id}")

    # Save to DB
    subscription = models.Subscription(
        caregiver_id=caregiver.id,
        razorpay_order_id=order_id,
        amount=amount,
        status="created"
    )
    db.add(subscription)
    db.commit()

    return {
        "razorpay_key_id": RAZORPAY_KEY_ID or "rzp_test_placeholder",
        "razorpay_order_id": order_id,
        "amount": amount,
        "currency": "INR"
    }


@app.post("/subscriptions/verify")
def verify_subscription(data: schemas.SubscriptionVerify, db: Session = Depends(get_db)):
    """Verify Razorpay payment signature and activate premium."""
    subscription = db.query(models.Subscription).filter(
        models.Subscription.razorpay_order_id == data.razorpay_order_id,
        models.Subscription.caregiver_id == data.caregiver_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription order not found")

    # Verify signature
    if RAZORPAY_KEY_SECRET and not RAZORPAY_KEY_SECRET.startswith("your_"):
        signature_payload = f"{data.razorpay_order_id}|{data.razorpay_payment_id}"
        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode('utf-8'),
            signature_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if expected_signature != data.razorpay_signature:
            subscription.status = "failed"
            db.commit()
            raise HTTPException(status_code=400, detail="Payment signature verification failed")
    else:
        logger.info(f"[MOCK RAZORPAY] Skipping signature verification for order {data.razorpay_order_id}")

    # Activate premium
    subscription.razorpay_payment_id = data.razorpay_payment_id
    subscription.razorpay_signature = data.razorpay_signature
    subscription.status = "paid"
    subscription.expires_at = datetime.utcnow() + timedelta(days=30)
    db.commit()

    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == data.caregiver_id).first()
    if caregiver:
        caregiver.is_premium = True
        caregiver.premium_expires_at = subscription.expires_at
        db.commit()
        logger.info(f"Premium activated for caregiver #{caregiver.id} until {subscription.expires_at}")

    return {"status": "success", "premium_until": str(subscription.expires_at)}


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")
def health_check():
    return {"status": "ok", "scheduler_running": scheduler.running}
