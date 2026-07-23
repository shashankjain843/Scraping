from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from backend.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    templates = relationship("RoleTemplate", back_populates="user", cascade="all, delete-orphan")
    drafts = relationship("EmailDraft", back_populates="user", cascade="all, delete-orphan")
    sent_logs = relationship("SentLog", back_populates="user", cascade="all, delete-orphan")

class OTPVerification(Base):
    __tablename__ = "otp_verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    otp = Column(String, nullable=False)
    purpose = Column(String, nullable=False) # 'register', 'forgot_password'
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_verified = Column(Boolean, default=False)

class UserSettings(Base):

    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    adzuna_app_id = Column(String, default="")
    adzuna_app_key = Column(String, default="")
    gemini_api_key = Column(String, default="")
    smtp_server = Column(String, default="smtp.gmail.com")
    smtp_port = Column(Integer, default=587)
    smtp_email = Column(String, default="")
    smtp_password = Column(String, default="")
    phone_number = Column(String, default="")
    linkedin_url = Column(String, default="")
    daily_send_limit = Column(Integer, default=30)
    tos_accepted = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="settings")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint('source', 'source_job_id', name='uix_source_job_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, default="adzuna", nullable=False)
    source_job_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=False) # display name from Adzuna
    city = Column(String, nullable=False, index=True) # matched canonical target city
    description = Column(Text, nullable=False)
    apply_url = Column(String, nullable=False)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    role_category = Column(String, nullable=False, index=True) # 'data_analyst' or 'data_scientist'
    bucket_0_1 = Column(Boolean, default=False, nullable=False) # 0-1 years
    bucket_1_3 = Column(Boolean, default=False, nullable=False) # 1-3 years (includes 1-2)
    created_at = Column(DateTime, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    drafts = relationship("EmailDraft", back_populates="job", cascade="all, delete-orphan")
    sent_logs = relationship("SentLog", back_populates="job", cascade="all, delete-orphan")

class RoleTemplate(Base):
    __tablename__ = "role_templates"
    __table_args__ = (
        UniqueConstraint('user_id', 'role_category', name='uix_user_role_template'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_category = Column(String, nullable=False) # 'data_analyst' or 'data_scientist'
    subject_template = Column(Text, nullable=False)
    body_template = Column(Text, nullable=False)
    resume_file_path = Column(String, nullable=True)
    resume_file_name = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="templates")

class EmailDraft(Base):
    __tablename__ = "email_drafts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String, default="draft", nullable=False) # 'draft', 'queued', 'sent', 'failed'
    send_after = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    draft_resume_path = Column(String, nullable=True) # Manually attached resume per draft
    draft_resume_name = Column(String, nullable=True)
    is_unmatched = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    
    user = relationship("User", back_populates="drafts")
    job = relationship("Job", back_populates="drafts")


class SentLog(Base):
    __tablename__ = "sent_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String, nullable=False) # 'sent' or 'failed'
    details = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="sent_logs")
    job = relationship("Job", back_populates="sent_logs")

class AdzunaQuotaLog(Base):
    __tablename__ = "adzuna_quota_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    endpoint = Column(String, nullable=False)
    records_count = Column(Integer, default=0, nullable=False)
