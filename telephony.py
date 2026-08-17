import os
import logging
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Load environment variables from .env if present
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL", "http://localhost:8000")

logger = logging.getLogger("med_reminder.telephony")

def get_twilio_client():
    """Helper to get an initialized Twilio Client or None if credentials missing."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or TWILIO_ACCOUNT_SID.startswith("your_"):
        logger.warning("Twilio credentials not configured or placeholder used.")
        return None
    try:
        return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        return None


def trigger_voice_call(patient_phone: str, tactile_marker: str, log_id: int, base_url: str = None) -> bool:
    """
    Triggers an outbound voice call to the patient.
    Sets the callback webhook to /voice-callback/{log_id}.
    """
    client = get_twilio_client()
    domain_url = base_url or BASE_WEBHOOK_URL
    callback_url = f"{domain_url}/voice-callback/{log_id}?marker={tactile_marker}"

    if not client:
        logger.info(f"[MOCK TWILIO CALL] Outbound call to {patient_phone} for log #{log_id} ({tactile_marker}). Callback: {callback_url}")
        return False

    try:
        call = client.calls.create(
            to=patient_phone,
            from_=TWILIO_PHONE_NUMBER,
            url=callback_url
        )
        logger.info(f"Twilio call initiated successfully. Call SID: {call.sid} to {patient_phone} for log #{log_id}")
        return True
    except TwilioRestException as e:
        logger.error(f"Twilio API Error triggering call to {patient_phone}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error triggering call to {patient_phone}: {e}")
        return False


def send_caregiver_sms(caregiver_phone: str, tactile_marker: str, patient_name: str = "Friend", language: str = "en") -> bool:
    """
    Sends an SMS alert to the caregiver when a dose is missed.
    Uses patient's actual name instead of clinical terms.
    Supports bilingual messages (English and Tamil).
    """
    client = get_twilio_client()

    if language == "ta":
        message_body = (
            f"அவசர எச்சரிக்கை: {patient_name} அவர்கள் {tactile_marker} எனக் குறிக்கப்பட்ட கொள்கலனில் உள்ள "
            f"மருந்தை எடுக்கவில்லை. உடனடியாக கவனிக்கவும்."
        )
    else:
        message_body = f"CRITICAL ALERT: {patient_name} missed the medication dose for {tactile_marker}. Please check on them immediately."

    if not client:
        logger.info(f"[MOCK TWILIO SMS] To: {caregiver_phone} Body: '{message_body}'")
        return False

    try:
        message = client.messages.create(
            to=caregiver_phone,
            from_=TWILIO_PHONE_NUMBER,
            body=message_body
        )
        logger.info(f"Twilio SMS sent to {caregiver_phone}. Message SID: {message.sid}")
        return True
    except TwilioRestException as e:
        logger.error(f"Twilio API Error sending SMS to {caregiver_phone}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending SMS to {caregiver_phone}: {e}")
        return False

