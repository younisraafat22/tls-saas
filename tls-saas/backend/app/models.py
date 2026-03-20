"""
SQLAlchemy ORM Models
All database tables for the TLS Appointment Checker SaaS.
"""

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum as SAEnum, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ── Enums ────────────────────────────────────────────────────────────

class ServiceType(str, enum.Enum):
    LEGALIZATION = "legalization"
    VISA = "visa"


class PlanType(str, enum.Enum):
    LEGALIZATION = "legalization"
    VISA = "visa"
    ALL_IN_ONE = "all_in_one"
    PREMIUM = "premium"


class SubscriptionStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PaymentMethod(str, enum.Enum):
    VODAFONE_CASH = "vodafone_cash"
    INSTAPAY = "instapay"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    WEB_PUSH = "web_push"


class NotificationLogStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"


# ── Utility ──────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Models ───────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    phone = Column(String(50), default="")
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    push_subscription = Column(JSON, nullable=True)  # Web Push subscription object
    created_at = Column(DateTime(timezone=True), default=utcnow)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user", lazy="selectin")
    payments = relationship("Payment", back_populates="user", lazy="selectin")
    branch_monitors = relationship("UserBranchMonitor", back_populates="user", lazy="selectin")
    notification_logs = relationship("NotificationLog", back_populates="user", lazy="selectin")



class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_type = Column(SAEnum(PlanType), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    price_monthly = Column(Float, nullable=False)
    currency = Column(String(10), default="EGP")
    features = Column(JSON, default=list)  # List of feature strings
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan", lazy="selectin")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.PENDING_PAYMENT)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    auto_renew = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    service_type = Column(SAEnum(ServiceType), nullable=False)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("name", "service_type", name="uq_branch_name_service"),
    )

    # Relationships
    check_results = relationship("CheckResult", back_populates="branch", lazy="selectin")
    service_accounts = relationship("ServiceAccount", back_populates="branch", lazy="selectin")
    user_monitors = relationship("UserBranchMonitor", back_populates="branch", lazy="selectin")


class UserBranchMonitor(Base):
    """Tracks which branches a user is monitoring."""
    __tablename__ = "user_branch_monitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "branch_id", name="uq_user_branch"),
    )

    user = relationship("User", back_populates="branch_monitors")
    branch = relationship("Branch", back_populates="user_monitors")


class ServiceAccount(Base):
    """TLS login credentials used by the server to check a branch."""
    __tablename__ = "service_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    email_encrypted = Column(Text, nullable=False)
    password_encrypted = Column(Text, nullable=False)
    is_primary = Column(Boolean, default=False)  # Admin's own account
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null if admin's
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, default="")

    branch = relationship("Branch", back_populates="service_accounts")
    owner = relationship("User", foreign_keys=[owner_user_id])


class CheckResult(Base):
    """Result of a branch availability check."""
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    checked_at = Column(DateTime(timezone=True), default=utcnow, index=True)
    slots_available = Column(Boolean, default=False)
    slot_details = Column(JSON, nullable=True)  # {"dates": [...], "count": N}
    screenshot_path = Column(String(500), default="")
    error = Column(Text, default="")
    duration_seconds = Column(Float, default=0)
    source = Column(String(20), default="server")  # "server" or "desktop"

    branch = relationship("Branch", back_populates="check_results")
    notification_logs = relationship("NotificationLog", back_populates="check_result", lazy="selectin")

    __table_args__ = (
        Index("ix_check_results_branch_time", "branch_id", "checked_at"),
        Index("ix_check_results_user_time", "user_id", "checked_at"),
    )


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    check_result_id = Column(Integer, ForeignKey("check_results.id", ondelete="CASCADE"), nullable=False)
    channel = Column(SAEnum(NotificationChannel), nullable=False)
    destination = Column(String(255), default="")  # email address, chat_id, etc.
    sent_at = Column(DateTime(timezone=True), default=utcnow)
    status = Column(SAEnum(NotificationLogStatus), default=NotificationLogStatus.SENT)
    error = Column(Text, default="")

    user = relationship("User", back_populates="notification_logs")
    check_result = relationship("CheckResult", back_populates="notification_logs")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="EGP")
    method = Column(SAEnum(PaymentMethod), default=PaymentMethod.VODAFONE_CASH)
    reference = Column(String(255), default="")  # Transaction ID from user
    status = Column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING)
    admin_notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)  # Branch user wants to monitor
    screenshot_data = Column(Text, nullable=True)  # Base64-encoded payment screenshot
    hardware_id = Column(String(100), nullable=True)  # Desktop app device binding
    plan_key = Column(String(50), nullable=True)   # e.g. "legalization_monthly", "premium"
    submitter_name = Column(String(255), nullable=True)  # For desktop submissions without account
    submitter_email = Column(String(255), nullable=True)  # For desktop submissions without account
    license_key = Column(String(255), nullable=True)  # Generated license key after approval

    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", foreign_keys=[subscription_id])
    branch = relationship("Branch", foreign_keys=[branch_id])


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserCredential(Base):
    """
    Stores a user's own TLS website credentials for a given service type.
    Used by the scheduler to run checks on behalf of the user.
    """
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    service_type = Column(SAEnum(ServiceType), nullable=False)
    email_encrypted = Column(Text, nullable=False)
    password_encrypted = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, default="")

    __table_args__ = (
        UniqueConstraint("user_id", "service_type", name="uq_user_credential_service"),
    )

    user = relationship("User", foreign_keys=[user_id])


class ActivityLog(Base):
    """Admin activity / audit trail."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # "payment_approved", "user_banned", etc.
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class AppRating(Base):
    __tablename__ = "app_ratings"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True, nullable=True)
    rating = Column(Integer, nullable=False) # 1 to 5
    comment = Column(Text, nullable=True)
    source = Column(String, default="website") # website or desktop
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class AppDownload(Base):
    __tablename__ = "app_downloads"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, nullable=True)
    version = Column(String, nullable=True)
    platform = Column(String, nullable=True) # windows, mac, linux
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class FoundAppointment(Base):
    __tablename__ = "found_appointments"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True, nullable=True)
    branch = Column(String, nullable=True)
    service_type = Column(String, nullable=True)
    found_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class HardwareUsage(Base):
    __tablename__ = "hardware_usage"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    hardware_id = Column(String(255), unique=True, index=True, nullable=False)
    checks_today = Column(Integer, default=0)
    last_reset_date = Column(String(20), nullable=True) # YYYY-MM-DD
