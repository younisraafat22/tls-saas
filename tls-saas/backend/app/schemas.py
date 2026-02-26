"""
Pydantic schemas for request/response validation.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.models import (
    PlanType, SubscriptionStatus, PaymentStatus, PaymentMethod,
    ServiceType, NotificationChannel,
)


# ── Auth ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(default="", max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class RefreshRequest(BaseModel):
    refresh_token: str


# ── User ─────────────────────────────────────────────────────────────

class UserPublic(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str
    is_active: bool
    is_admin: bool
    has_push_subscription: bool = False
    created_at: datetime
    active_plan: Optional[str] = None
    subscription_expires: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class PushSubscriptionRequest(BaseModel):
    subscription: dict  # Web Push subscription JSON


# ── Plans ────────────────────────────────────────────────────────────

class PlanPublic(BaseModel):
    id: int
    plan_type: PlanType
    display_name: str
    description: str
    price_monthly: float
    currency: str
    features: list
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class PlanUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    features: Optional[list] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


# ── Subscription ─────────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    plan_type: PlanType


class SubscriptionPublic(BaseModel):
    id: int
    user_id: int
    plan: PlanPublic
    status: SubscriptionStatus
    starts_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Branches ─────────────────────────────────────────────────────────

class BranchPublic(BaseModel):
    id: int
    name: str
    url: str
    service_type: ServiceType
    is_active: bool
    subscriber_count: int = 0
    last_check: Optional[datetime] = None
    last_status: Optional[bool] = None

    class Config:
        from_attributes = True


class BranchMonitorRequest(BaseModel):
    branch_ids: list[int]


# ── Check Results ────────────────────────────────────────────────────

class CheckResultPublic(BaseModel):
    id: int
    branch_name: str
    branch_service_type: ServiceType
    checked_at: datetime
    slots_available: bool
    slot_details: Optional[dict] = None
    duration_seconds: float
    error: str

    class Config:
        from_attributes = True


# ── Payments ─────────────────────────────────────────────────────────

class UserCredentialCreate(BaseModel):
    service_type: ServiceType
    tls_email: str = Field(min_length=1, max_length=255)
    tls_password: str = Field(min_length=1, max_length=255)


class UserCredentialPublic(BaseModel):
    id: int
    service_type: ServiceType
    email_masked: str  # first 3 chars + ***
    has_credential: bool = True
    last_used_at: Optional[datetime] = None
    last_error: str = ""

    class Config:
        from_attributes = True


class PaymentSubmitRequest(BaseModel):
    plan_type: PlanType
    branch_id: int
    method: PaymentMethod
    reference: str = Field(default="", max_length=255, description="Transaction ID / reference")
    screenshot_data: Optional[str] = Field(default=None, description="Base64-encoded screenshot")
    amount: float
    # TLS credentials collected at payment time
    tls_email: str = Field(min_length=1, max_length=255, description="User's TLS website email")
    tls_password: str = Field(min_length=1, max_length=255, description="User's TLS website password")


class PaymentPublic(BaseModel):
    id: int
    user_id: int
    user_email: str = ""
    user_name: str = ""
    amount: float
    currency: str
    method: PaymentMethod
    reference: str
    screenshot_data: Optional[str] = None
    status: PaymentStatus
    admin_notes: str
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    # Desktop submission fields
    hardware_id: Optional[str] = None
    plan_key: Optional[str] = None
    submitter_name: Optional[str] = None
    submitter_email: Optional[str] = None
    license_key: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DesktopPaymentSubmit(BaseModel):
    """Submit a payment from the desktop app (no JWT required)."""
    plan_key: str = Field(description="e.g. legalization_monthly, visa_monthly, premium")
    hardware_id: str = Field(min_length=1, max_length=100, description="Unique device fingerprint")
    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=1, max_length=255)
    payment_method: str = Field(description="vodafone_cash or instapay")
    reference: str = Field(default="", max_length=255, description="Transaction reference / number")
    screenshot_b64: str = Field(default="", description="Base64-encoded payment screenshot")
    amount: float


class PaymentApproveRequest(BaseModel):
    admin_notes: str = ""
    months: int = Field(default=1, ge=1, le=12, description="Number of months to activate")


class PaymentRejectRequest(BaseModel):
    admin_notes: str = ""


# ── Notifications ────────────────────────────────────────────────────

class NotificationPreferences(BaseModel):
    email_enabled: bool = True
    push_enabled: bool = False


class NotificationLogPublic(BaseModel):
    id: int
    channel: NotificationChannel
    destination: str
    sent_at: datetime
    status: str
    branch_name: str = ""

    class Config:
        from_attributes = True


# ── Service Accounts (Admin) ────────────────────────────────────────

class ServiceAccountCreate(BaseModel):
    branch_id: int
    email: str
    password: str
    is_primary: bool = True


class ServiceAccountPublic(BaseModel):
    id: int
    branch_id: int
    branch_name: str = ""
    email_masked: str  # Show only first 3 chars + ***
    is_primary: bool
    is_active: bool
    last_used_at: Optional[datetime]
    last_error: str

    class Config:
        from_attributes = True


# ── Admin Dashboard ──────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_users: int
    active_subscriptions: int
    pending_payments: int
    total_revenue: float
    checks_today: int
    slots_found_today: int
    active_branches: int
    notifications_sent_today: int


class SystemSettingUpdate(BaseModel):
    key: str
    value: str


class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


# ── Desktop App ──────────────────────────────────────────────────────

class DesktopCheckReport(BaseModel):
    """Report from the desktop app after a local TLS check."""
    branch_name: str
    service_type: str
    slots_available: bool
    slot_details: str = ""
    screenshot_b64: str = ""
    duration_seconds: float = 0
    error: str = ""


class AppVersionResponse(BaseModel):
    """Version info for desktop app auto-update."""
    version: str
    download_url: str = ""
    release_notes: str = ""
    force_update: bool = False


# ── Generic ──────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int


# Fix forward reference for TokenResponse
TokenResponse.model_rebuild()
