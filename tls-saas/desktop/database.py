"""
Database Models
SQLAlchemy models for user management, licenses, and settings
"""
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config
import bcrypt
import secrets
import json

Base = declarative_base()

class User(Base):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    birth_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(100), nullable=True)
    password_reset_token = Column(String(100), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    is_premium = Column(Boolean, default=False)
    license_key = Column(String(100), unique=True, nullable=True)
    subscription_plan = Column(String(50), default='trial')  # trial, basic, pro, unlimited
    checks_today = Column(Integer, default=0)
    checks_reset_date = Column(DateTime, default=datetime.utcnow)
    
    def get_daily_check_limit(self) -> int:
        """Get daily check limit based on plan"""
        limits = {
            'trial': 10,
            'basic': 50,
            'pro': 200,
            'unlimited': 999999
        }
        return limits.get(self.subscription_plan, 10)
    
    def can_start_monitoring(self) -> tuple[bool, str]:
        """Check if user can start monitoring based on plan limits"""
        # Reset daily counter if new day
        if self.checks_reset_date.date() < datetime.utcnow().date():
            self.checks_today = 0
            self.checks_reset_date = datetime.utcnow()
        
        limit = self.get_daily_check_limit()
        if self.checks_today >= limit:
            return False, f"Daily limit reached ({limit} checks). Upgrade your plan for more checks."
        return True, ""
    
    def increment_daily_checks(self):
        """Increment daily check counter"""
        if self.checks_reset_date.date() < datetime.utcnow().date():
            self.checks_today = 1
            self.checks_reset_date = datetime.utcnow()
        else:
            self.checks_today += 1
    
    def set_password(self, password: str):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password: str) -> bool:
        """Verify password"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def is_trial_active(self) -> bool:
        """Check if trial period is active"""
        if self.is_premium:
            return True
        if self.trial_ends_at and datetime.utcnow() < self.trial_ends_at:
            return True
        return False
    
    def get_days_remaining(self) -> int:
        """Get remaining trial days"""
        if self.is_premium:
            return -1  # Unlimited
        if self.trial_ends_at:
            delta = self.trial_ends_at - datetime.utcnow()
            return max(0, delta.days)
        return 0
    
    def activate_trial(self):
        """Activate trial period"""
        if not self.trial_ends_at:
            self.trial_ends_at = datetime.utcnow() + timedelta(days=Config.TRIAL_DAYS)
    
    def activate_premium(self, license_key: str):
        """Activate premium with license key"""
        self.is_premium = True
        self.license_key = license_key


class UserSettings(Base):
    """User settings for TLS checking"""
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # TLS Credentials (encrypted)
    tls_email = Column(String(255), nullable=True)
    tls_password = Column(Text, nullable=True)  # Encrypted
    
    # Service type: 'legalization' or 'visa'
    service_type = Column(String(50), default='legalization')

    # Check Settings
    check_interval = Column(Integer, default=Config.DEFAULT_CHECK_INTERVAL)  # minutes
    is_monitoring = Column(Boolean, default=False)
    last_check_at = Column(DateTime, nullable=True)
    total_checks = Column(Integer, default=0)
    branch = Column(String(255), nullable=True)
    branch_url = Column(String(500), nullable=True)
    
    # Notification Settings
    notification_email = Column(String(255), nullable=True)
    enable_email_notifications = Column(Boolean, default=True)
    enable_windows_notifications = Column(Boolean, default=True)
    enable_mobile_notifications = Column(Boolean, default=False)
    
    # Credential Options
    use_same_credentials = Column(Boolean, default=False)
    headless_mode = Column(Boolean, default=True)
    first_check_done = Column(Boolean, default=False)
    
    # Status Report
    last_status_report = Column(DateTime, nullable=True)
    last_slots_found = Column(Boolean, default=False)
    
    # Email change tracking (for license limits)
    email_history = Column(Text, default="[]")  # JSON array of email changes with timestamps
    email_change_count = Column(Integer, default=0)  # Track number of notification email changes

    # TLS credential email change tracking
    tls_email_history = Column(Text, default="[]")  # JSON array of TLS email changes
    tls_email_change_count = Column(Integer, default=0)  # Track TLS email changes
    
    def get_notification_types(self) -> list:
        """Get enabled notification types"""
        types = []
        if self.enable_email_notifications:
            types.append("email")
        if self.enable_windows_notifications:
            types.append("windows")
        if self.enable_mobile_notifications:
            types.append("mobile")
        return types


class CheckHistory(Base):
    """History of appointment checks"""
    __tablename__ = 'check_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    checked_at = Column(DateTime, default=datetime.utcnow)
    slots_available = Column(Boolean, default=False)
    message = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)


class License(Base):
    """License keys for premium access"""
    __tablename__ = 'licenses'
    
    id = Column(Integer, primary_key=True)
    license_key = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    activated_by_user_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    duration_days = Column(Integer, default=365)  # 1 year default
    expires_at = Column(DateTime, nullable=True)
    
    @staticmethod
    def generate_license_key() -> str:
        """Generate a unique license key"""
        # Format: XXXX-XXXX-XXXX-XXXX
        parts = [secrets.token_hex(2).upper() for _ in range(4)]
        return '-'.join(parts)


# Database setup
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """Initialize database"""
    Base.metadata.create_all(bind=engine)
    migrate_database()
    print("[OK] Database initialized successfully")

def migrate_database():
    """Migrate existing database to add new columns"""
    db = SessionLocal()
    try:
        # Check if new columns exist, if not add them
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        # Add subscription_plan column if missing
        if 'subscription_plan' not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN subscription_plan VARCHAR(50) DEFAULT 'trial'"))
            db.commit()
            print("[OK] Added subscription_plan column")
        
        # Add checks_today column if missing
        if 'checks_today' not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN checks_today INTEGER DEFAULT 0"))
            db.commit()
            print("[OK] Added checks_today column")
        
        # Refresh column list
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        # Add checks_reset_date column if missing (SQLite compatible)
        if 'checks_reset_date' not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN checks_reset_date DATETIME"))
            db.commit()
            # Update existing rows with current timestamp
            db.execute(text("UPDATE users SET checks_reset_date = datetime('now') WHERE checks_reset_date IS NULL"))
            db.commit()
            print("[OK] Added checks_reset_date column")
        
        # Migrate user_settings table
        settings_columns = [col['name'] for col in inspector.get_columns('user_settings')]
        
        # Add branch column if missing
        if 'branch' not in settings_columns:
            db.execute(text("ALTER TABLE user_settings ADD COLUMN branch VARCHAR(255)"))
            db.commit()
            print("[OK] Added branch column to user_settings")
        
        # Add branch_url column if missing
        if 'branch_url' not in settings_columns:
            db.execute(text("ALTER TABLE user_settings ADD COLUMN branch_url VARCHAR(500)"))
            db.commit()
            print("[OK] Added branch_url column to user_settings")

        # Add service_type column if missing
        settings_columns = [col['name'] for col in inspector.get_columns('user_settings')]
        if 'service_type' not in settings_columns:
            db.execute(text("ALTER TABLE user_settings ADD COLUMN service_type VARCHAR(50) DEFAULT 'legalization'"))
            db.commit()
            print("[OK] Added service_type column to user_settings")

        # Add email_history column if missing
        settings_columns = [col['name'] for col in inspector.get_columns('user_settings')]
        if 'email_history' not in settings_columns:
            db.execute(text("ALTER TABLE user_settings ADD COLUMN email_history TEXT DEFAULT '[]'"))
            db.commit()
            print("[OK] Added email_history column to user_settings")

        # Add email_change_count column if missing
        settings_columns = [col['name'] for col in inspector.get_columns('user_settings')]
        if 'email_change_count' not in settings_columns:
            db.execute(text("ALTER TABLE user_settings ADD COLUMN email_change_count INTEGER DEFAULT 0"))
            db.commit()
            print("[OK] Added email_change_count column to user_settings")

        # Add tls_email_change_count column if missing
        settings_columns = [col['name'] for col in inspector.get_columns('user_settings')]
        if 'tls_email_change_count' not in settings_columns:
            db.execute(text("ALTER TABLE user_settings ADD COLUMN tls_email_change_count INTEGER DEFAULT 0"))
            db.commit()
            print("[OK] Added tls_email_change_count column to user_settings")

        # Add tls_email_history column if missing
        settings_columns = [col['name'] for col in inspector.get_columns('user_settings')]
        if 'tls_email_history' not in settings_columns:
            db.execute(text("ALTER TABLE user_settings ADD COLUMN tls_email_history TEXT DEFAULT '[]'"))
            db.commit()
            print("[OK] Added tls_email_history column to user_settings")

    except Exception as e:
        db.rollback()
        print(f"[INFO] Migration note: {e}")
    finally:
        db.close()

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let caller handle it

def create_admin_licenses(count: int = 10):
    """Create initial license keys for distribution"""
    db = SessionLocal()
    try:
        licenses = []
        for _ in range(count):
            license_key = License.generate_license_key()
            license_obj = License(license_key=license_key)
            db.add(license_obj)
            licenses.append(license_key)
        db.commit()
        print(f"[OK] Generated {count} license keys:")
        for key in licenses:
            print(f"   {key}")
        return licenses
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error creating licenses: {e}")
        return []
    finally:
        db.close()
