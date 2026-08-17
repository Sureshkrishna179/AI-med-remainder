from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# Caregiver Schemas
class CaregiverCreate(BaseModel):
    caregiver_name: str
    caregiver_phone: str
    caregiver_whatsapp: Optional[str] = None
    patient_name: str
    patient_phone: str
    language: Optional[str] = "en"
    passcode: Optional[str] = None
    consent_accepted: bool = False

class CaregiverLogin(BaseModel):
    caregiver_phone: str
    passcode: str

class CaregiverResponse(BaseModel):
    id: int
    caregiver_name: str
    caregiver_phone: str
    caregiver_whatsapp: Optional[str] = None
    patient_name: str
    patient_phone: str
    language: str
    is_premium: bool
    premium_expires_at: Optional[datetime] = None
    consent_accepted: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Schedule Schemas
class ScheduleCreate(BaseModel):
    caregiver_id: int
    med_name: str
    time_str: str  # Format: "HH:MM" e.g., "08:00"
    tactile_marker: str  # e.g., "1 Rubber Band"
    food_instruction: Optional[str] = "Any Time"
    quantity: Optional[str] = "1 Tablet"
    bottle_image_url: Optional[str] = None
    is_active: Optional[bool] = True

class ScheduleUpdate(BaseModel):
    """Schema for editing an existing schedule."""
    med_name: Optional[str] = None
    time_str: Optional[str] = None
    tactile_marker: Optional[str] = None
    food_instruction: Optional[str] = None
    quantity: Optional[str] = None
    bottle_image_url: Optional[str] = None
    is_active: Optional[bool] = None

class ScheduleResponse(BaseModel):
    id: int
    caregiver_id: int
    med_name: str
    time_str: str
    tactile_marker: str
    food_instruction: Optional[str] = "Any Time"
    quantity: Optional[str] = "1 Tablet"
    bottle_image_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# AdherenceLog Schemas
class AdherenceLogResponse(BaseModel):
    id: int
    schedule_id: int
    timestamp: datetime
    status: str
    retry_count: int
    acknowledged_by_caregiver: bool = False
    med_name: Optional[str] = None
    tactile_marker: Optional[str] = None
    food_instruction: Optional[str] = None
    quantity: Optional[str] = None

    class Config:
        from_attributes = True


# Subscription Schemas
class SubscriptionCreateOrder(BaseModel):
    caregiver_id: int

class SubscriptionVerify(BaseModel):
    caregiver_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class SubscriptionResponse(BaseModel):
    id: int
    caregiver_id: int
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    amount: int
    status: str
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True
