import os
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models import User, UserSettings, Job, RoleTemplate, EmailDraft, SentLog
from backend.schemas import EmailDraftOut, JobOut
from backend.routers.auth import get_current_user
from backend.services.email_extractor import extract_emails_from_text
from backend.services.email_service import send_email_now, approve_and_send_batch
from backend.services.adzuna_service import fetch_adzuna_jobs
from backend.services.job_parser import parse_city, parse_experience, parse_role_category
from backend.config import settings

router = APIRouter(prefix="/api/assistant", tags=["Application Assistant"])

class SearchRequest(BaseModel):
    role: str # e.g. "Frontend Developer", "Data Analyst", "Data Scientist"
    location: str # e.g. "Jaipur", "Noida", "Gurgaon", "Remote", "Bangalore"

class SearchResponse(BaseModel):
    extractable_count: int
    manual_followup_count: int
    drafts: List[EmailDraftOut]
    manual_followup_jobs: List[JobOut]

@router.post("/search", response_model=SearchResponse)
def search_and_extract(
    req: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search & Match step + Email Extraction step + Draft Generation + Manual Follow-up grouping.
    Extracts emails ONLY from visible job description text via regex.
    Auto-attaches user's stored profile resume if available.
    """
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()

    # 1. Fetch fresh jobs from Adzuna API matching criteria if available
    try:
        app_id = (user_settings.adzuna_app_id if user_settings and user_settings.adzuna_app_id else settings.ADZUNA_APP_ID)
        app_key = (user_settings.adzuna_app_key if user_settings and user_settings.adzuna_app_key else settings.ADZUNA_APP_KEY)
        if app_id and app_key:
            fetch_adzuna_jobs(db, app_id, app_key)
    except Exception:
        pass # Continue with database jobs

    # 2. Query jobs matching role & location
    query = db.query(Job)

    # Location filter
    canonical_city = parse_city(req.location)
    if canonical_city:
        query = query.filter(Job.city == canonical_city)
    else:
        query = query.filter(Job.location.ilike(f"%{req.location}%"))

    # Role filter
    role_cat = parse_role_category(req.role)
    if role_cat and role_cat != "unmatched":
        query = query.filter(Job.role_category == role_cat)
    else:
        query = query.filter(Job.title.ilike(f"%{req.role}%"))

    jobs = query.order_by(desc(Job.fetched_at)).limit(20).all()

    # Find user's stored default profile resume file if uploaded
    stored_resume_path = None
    stored_resume_name = None

    # Check uploads directory for any resume for this user
    for role_t in ["data_analyst", "data_scientist"]:
        rt = db.query(RoleTemplate).filter(RoleTemplate.user_id == current_user.id, RoleTemplate.role_category == role_t).first()
        if rt and rt.resume_file_path and os.path.exists(rt.resume_file_path):
            stored_resume_path = rt.resume_file_path
            stored_resume_name = rt.resume_file_name
            break

    generated_drafts = []
    manual_followup_jobs = []

    # Candidate name
    user_name = (user_settings.full_name if user_settings and user_settings.full_name else current_user.full_name) or "Applicant"

    for job in jobs:
        # Step 3: Extract email from job description text ONLY via regex
        found_emails = extract_emails_from_text(job.description)

        if found_emails:
            recipient_email = found_emails[0] # Use first found email in description text

            # Check if draft already exists
            existing = db.query(EmailDraft).filter(
                EmailDraft.user_id == current_user.id,
                EmailDraft.job_id == job.id,
                EmailDraft.status.in_(["draft", "failed"])
            ).first()

            if not existing:
                # Step 5: Draft Generation Step using specified template
                subject = f"Application for {job.title} at {job.company}"
                body = (
                    f"Hi,\n\n"
                    f"I'm applying for the {job.title} role at {job.company}. Please find my resume attached.\n"
                    f"I believe my background in {req.role} makes me a strong fit for this position.\n\n"
                    f"Looking forward to hearing from you.\n\n"
                    f"Regards,\n"
                    f"{user_name}"
                )

                draft = EmailDraft(
                    user_id=current_user.id,
                    job_id=job.id,
                    recipient_email=recipient_email,
                    subject=subject,
                    body=body,
                    status="draft",
                    draft_resume_path=stored_resume_path,
                    draft_resume_name=stored_resume_name,
                    is_unmatched=False
                )
                db.add(draft)
                db.commit()
                db.refresh(draft)
                existing = draft

            generated_drafts.append(
                EmailDraftOut(
                    id=existing.id,
                    job_id=existing.job_id,
                    recipient_email=existing.recipient_email,
                    subject=existing.subject,
                    body=existing.body,
                    status=existing.status,
                    send_after=existing.send_after,
                    sent_at=existing.sent_at,
                    error_message=existing.error_message,
                    resume_name=existing.draft_resume_name,
                    is_unmatched=existing.is_unmatched,
                    created_at=existing.created_at,
                    job_title=job.title,
                    company_name=job.company,
                    role_category=job.role_category
                )
            )
        else:
            # Step 3 (No email found): Mark as "no_email_found" and group in manual follow-up list
            manual_followup_jobs.append(
                JobOut(
                    id=job.id,
                    source=job.source,
                    source_job_id=job.source_job_id,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    city=job.city,
                    description=job.description,
                    apply_url=job.apply_url,
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                    role_category=job.role_category,
                    bucket_0_1=job.bucket_0_1,
                    bucket_1_3=job.bucket_1_3,
                    created_at=job.created_at,
                    fetched_at=job.fetched_at
                )
            )

    return SearchResponse(
        extractable_count=len(generated_drafts),
        manual_followup_count=len(manual_followup_jobs),
        drafts=generated_drafts,
        manual_followup_jobs=manual_followup_jobs
    )
