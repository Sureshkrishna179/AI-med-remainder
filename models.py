from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Caregiver(Base):
    """
    The caregiver who registers, manages schedules, and receives alerts.
    This is the primary user of the dashboard.
    """
    __tablename__ = "caregivers"

    id = Column(Integer, primary_key=True, index=True)
    # Auth
    passcode = Column(String, nullable=True)  # Simple PIN login for V1
    email = Column(String, nullable=True, unique=True)
    # Caregiver info
    caregiver_name = Column(String, nullable=False)
    caregiver_phone = Column(String, nullable=False)
    caregiver_whatsapp = Column(String, nullable=True)
    # Patient (parent) info
    patient_name = Column(String, nullable=False, default="Friend")
    patient_phone = Column(String, nullable=False)
    # Preferences
    language = Column(String, default="en")
    # Subscription
    is_premium = Column(Boolean, default=False)
    premium_expires_at = Column(DateTime, nullable=True)
    # Legal
    consent_accepted = Column(Boolean, default=False)
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    schedules = relationship("Schedule", back_populates="caregiver", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="caregiver", cascade="all, delete-orphan")


class Schedule(Base):
    """
    A single medication schedule entry with time, tactile marker,
    food instructions, dosage quantity, and optional bottle photo.
    """
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    caregiver_id = Column(Integer, ForeignKey("caregivers.id"), nullable=False)
    med_name = Column(String, nullable=False)
    time_str = Column(String, nullable=False)  # Format: "HH:MM" e.g., "08:00"
    tactile_marker = Column(String, nullable=False)  # e.g., "1 Rubber Band"
    food_instruction = Column(String, default="Any Time")  # "Before Food", "After Food", "With Food", "Any Time"
    quantity = Column(String, default="1 Tablet")  # e.g., "2 Tablets", "10 ml", "1 Capsule"
    bottle_image_url = Column(String, nullable=True)  # Path to uploaded bottle photo
    is_active = Column(Boolean, default=True)

    caregiver = relationship("Caregiver", back_populates="schedules")
    logs = relationship("AdherenceLog", back_populates="schedule", cascade="all, delete-orphan")


class AdherenceLog(Base):
    """
    Tracks each medication event: Pending → Confirmed or Missed.
    Missed logs can be acknowledged by the caregiver.
    """
    __tablename__ = "adherence_logs"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="Pending")  # "Pending", "Confirmed", "Missed"
    retry_count = Column(Integer, default=0)
    acknowledged_by_caregiver = Column(Boolean, default=False)  # Caregiver acknowledged missed dose

    schedule = relationship("Schedule", back_populates="logs")


class Subscription(Base):
    """
    Tracks Razorpay payment records for premium subscriptions.
    """
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    caregiver_id = Column(Integer, ForeignKey("caregivers.id"), nullable=False)
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    razorpay_signature = Column(String, nullable=True)
    amount = Column(Integer, default=19900)  # Amount in paise (₹199 = 19900 paise)
    status = Column(String, default="created")  # "created", "paid", "failed"
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    caregiver = relationship("Caregiver", back_populates="subscriptions")
