from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr

# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OTPRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    full_name: Optional[str] = None

class OTPRegisterVerify(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    otp: str

class OTPPasswordReset(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class Token(BaseModel):

    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True

# User Settings Schemas
class UserSettingsOut(BaseModel):
    adzuna_app_id: str
    adzuna_app_key: str
    gemini_api_key: str
    smtp_server: str
    smtp_port: int
    smtp_email: str
    smtp_password_set: bool # don't send actual password in cleartext to UI
    phone_number: str
    linkedin_url: str
    daily_send_limit: int
    tos_accepted: bool

    class Config:
        from_attributes = True

class UserSettingsUpdate(BaseModel):
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_email: Optional[str] = None
    smtp_password: Optional[str] = None
    phone_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    daily_send_limit: Optional[int] = None
    tos_accepted: Optional[bool] = None


# Job Schemas
class JobOut(BaseModel):
    id: int
    source: str
    source_job_id: str
    title: str
    company: str
    location: str
    city: str
    description: str
    apply_url: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    role_category: str
    bucket_0_1: bool
    bucket_1_3: bool
    created_at: datetime
    fetched_at: datetime

    class Config:
        from_attributes = True

# Role Template Schemas
class RoleTemplateOut(BaseModel):
    id: int
    role_category: str
    subject_template: str
    body_template: str
    resume_file_name: Optional[str] = None
    has_resume: bool
    updated_at: datetime

    class Config:
        from_attributes = True

class RoleTemplateUpdate(BaseModel):
    subject_template: str
    body_template: str

# Email Draft Schemas
class EmailDraftCreate(BaseModel):
    job_id: int
    recipient_email: EmailStr

class EmailDraftUpdate(BaseModel):
    subject: str
    body: str

class EmailDraftOut(BaseModel):
    id: int
    job_id: int
    recipient_email: str
    subject: str
    body: str
    status: str
    send_after: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    resume_name: Optional[str] = None
    is_unmatched: bool = False
    created_at: datetime
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    role_category: Optional[str] = None



    class Config:
        from_attributes = True

# Sent Log Schemas
class SentLogOut(BaseModel):
    id: int
    job_id: int
    recipient_email: str
    subject: str
    body: str
    status: str
    details: Optional[str] = None
    sent_at: datetime
    job_title: Optional[str] = None
    company_name: Optional[str] = None

    class Config:
        from_attributes = True

# AI Cover Note Schemas
class AICoverNoteRequest(BaseModel):
    job_id: int

class AICoverNoteResponse(BaseModel):
    job_id: int
    job_title: str
    company: str
    cover_note: str
