import os
import time
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import User, UserSettings, Job, RoleTemplate, EmailDraft, SentLog

from backend.services.resume_parser import extract_name_from_resume

logger = logging.getLogger("email_service")

DEFAULT_TEMPLATES = {
    "data_analyst": {
        "subject": "Application for Data Analyst Position – {{user_name}}",
        "body": (
            "Dear Hiring Team,\n\n"
            "I am writing to express my interest in the Data Analyst position at {{company}}.\n"
            "With a strong foundation in SQL, Excel, and data visualization tools (Power BI/Tableau),\n"
            "I am confident in my ability to contribute to your team's data-driven decision-making.\n\n"
            "I have attached my resume for your review and would welcome the opportunity to discuss\n"
            "how my skills align with your requirements.\n\n"
            "Thank you for considering my application.\n\n"
            "Best regards,\n"
            "{{user_name}}\n"
            "{{phone_number}}\n"
            "{{linkedin_url}}"
        )
    },
    "data_scientist": {
        "subject": "Application for Data Scientist Position – {{user_name}}",
        "body": (
            "Dear Hiring Team,\n\n"
            "I am reaching out to apply for the Data Scientist position at {{company}}.\n"
            "My background in Python, machine learning, and statistical modeling has equipped\n"
            "me to build data-driven solutions that deliver measurable business impact.\n\n"
            "Please find my resume attached for your reference. I would be glad to discuss\n"
            "how my experience can add value to your team.\n\n"
            "Thank you for your time and consideration.\n\n"
            "Best regards,\n"
            "{{user_name}}\n"
            "{{phone_number}}\n"
            "{{linkedin_url}}"
        )
    }
}

OPT_OUT_FOOTER = "\n\n---\nIf you'd prefer not to receive applications like this, please let us know by replying to this email."

def check_spam_trigger_words(subject: str, body: str) -> Optional[str]:
    """Returns warning message if subject or body contains aggressive spam trigger words."""
    spam_words = ["URGENT", "100% FREE", "GUARANTEED JOB", "CLICK HERE IMMEDIATELY"]
    for w in spam_words:
        if w in subject.upper() or w in body.upper():
            return f"Spam Trigger Warning: Email contains promotional keyword '{w}'."
    if subject.isupper() and len(subject) > 10:
        return "Spam Trigger Warning: Subject line is in ALL CAPS."
    return None

def render_email_template(template_str: str, user: User, job: Job, user_settings: Optional[UserSettings] = None, resume_name: str = "") -> str:
    """Replaces placeholders in template string with actual user, job, and contact values."""
    candidate_name = resume_name or (user_settings.full_name if user_settings and user_settings.full_name else user.full_name)
    phone = user_settings.phone_number if user_settings and user_settings.phone_number else ""
    linkedin = user_settings.linkedin_url if user_settings and user_settings.linkedin_url else ""

    replacements = {
        "{{company}}": job.company,
        "{{job_title}}": job.title,
        "{{city}}": job.city,
        "{{location}}": job.location,
        "{{user_name}}": candidate_name,
        "{{user_email}}": user.email,
        "{{phone_number}}": phone,
        "{{linkedin_url}}": linkedin,
        "[Company Name]": job.company,
        "[Your Name]": candidate_name,
        "[Phone Number]": phone,
        "[LinkedIn/Portfolio Link]": linkedin,
    }
    
    result = template_str
    for key, val in replacements.items():
        result = result.replace(key, str(val))
    return result


def create_draft(db: Session, user: User, job: Job, recipient_email: str) -> EmailDraft:
    """Creates a new EmailDraft staged for human review without auto-attaching resume."""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()

    # Find user template for role category
    role_cat = job.role_category if job.role_category in DEFAULT_TEMPLATES else "data_analyst"
    is_unmatched = (job.role_category == "unmatched")

    role_template = db.query(RoleTemplate).filter(
        RoleTemplate.user_id == user.id,
        RoleTemplate.role_category == role_cat
    ).first()

    if role_template and role_template.subject_template and role_template.body_template:
        subject_t = role_template.subject_template
        body_t = role_template.body_template
    else:
        def_t = DEFAULT_TEMPLATES.get(role_cat, DEFAULT_TEMPLATES["data_analyst"])
        subject_t = def_t["subject"]
        body_t = def_t["body"]

    rendered_subject = render_email_template(subject_t, user, job, user_settings)
    rendered_body = render_email_template(body_t, user, job, user_settings)

    draft = EmailDraft(
        user_id=user.id,
        job_id=job.id,
        recipient_email=recipient_email,
        subject=rendered_subject,
        body=rendered_body,
        status="draft",
        is_unmatched=is_unmatched,
        draft_resume_path=None, # Resume must be manually attached by user per draft
        draft_resume_name=None
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def send_email_now(db: Session, draft_id: int) -> Dict[str, Any]:
    """
    Sends an email draft via standard SMTP upon explicit user action.
    Attaches the manually provided draft resume if available on the draft.
    Enforces per-user daily send limit (max 30 emails/day).
    """
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        return {"status": "error", "message": "Draft not found."}

    user = db.query(User).filter(User.id == draft.user_id).first()
    job = db.query(Job).filter(Job.id == draft.job_id).first()
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()

    # 1. Enforce Per-User Daily Send Limit Check (Max 30 emails / 24 hrs)
    daily_limit = user_settings.daily_send_limit if (user_settings and user_settings.daily_send_limit) else 30
    cutoff = datetime.utcnow() - timedelta(hours=24)
    sent_count_today = db.query(SentLog).filter(
        SentLog.user_id == user.id,
        SentLog.sent_at >= cutoff,
        SentLog.status == "sent"
    ).count()

    if sent_count_today >= daily_limit:
        err = f"Daily send limit reached ({sent_count_today}/{daily_limit} emails sent in last 24h). Sending paused to protect SMTP reputation."
        draft.status = "failed"
        draft.error_message = err
        db.commit()
        return {"status": "error", "message": err}

    # 2. Determine SMTP config
    smtp_server = (user_settings.smtp_server if user_settings and user_settings.smtp_server else settings.SMTP_SERVER)
    smtp_port = (user_settings.smtp_port if user_settings and user_settings.smtp_port else settings.SMTP_PORT)
    smtp_email = (user_settings.smtp_email if user_settings and user_settings.smtp_email else settings.SMTP_EMAIL) or user.email
    smtp_password = (user_settings.smtp_password if user_settings and user_settings.smtp_password else settings.SMTP_PASSWORD)

    if not smtp_server or not smtp_email or not smtp_password:
        err = "SMTP configuration incomplete. Please update SMTP settings in Settings."
        draft.status = "failed"
        draft.error_message = err
        db.commit()
        return {"status": "error", "message": err}

    # Extract resume name if present
    resume_candidate_name = ""
    if draft.draft_resume_path:
        resume_candidate_name = extract_name_from_resume(draft.draft_resume_path, default_name=user.full_name)

    # Re-render subject/body with resume name if extracted
    final_subject = render_email_template(draft.subject, user, job, user_settings, resume_candidate_name)
    final_body = render_email_template(draft.body, user, job, user_settings, resume_candidate_name)

    # Append professional opt-out footer
    if OPT_OUT_FOOTER not in final_body:
        final_body += OPT_OUT_FOOTER

    # Construct MIME message
    msg = MIMEMultipart()
    msg['From'] = smtp_email
    msg['To'] = draft.recipient_email
    msg['Subject'] = final_subject
    msg['Reply-To'] = user.email

    msg.attach(MIMEText(final_body, 'plain'))

    # Attach manually selected resume file if present on this specific draft
    if draft.draft_resume_path and os.path.exists(draft.draft_resume_path):
        try:
            with open(draft.draft_resume_path, 'rb') as f:
                attach = MIMEApplication(f.read(), _subtype="octet-stream")
                filename = draft.draft_resume_name or "Resume.pdf"
                attach.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(attach)
        except Exception as ex:
            logger.error(f"Error attaching draft resume: {str(ex)}")

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()

        # Update draft & sent log
        draft.status = "sent"
        draft.sent_at = datetime.utcnow()
        draft.error_message = None

        sent_log = SentLog(
            user_id=user.id,
            job_id=job.id,
            recipient_email=draft.recipient_email,
            subject=final_subject,
            body=final_body,
            status="sent",
            details="Sent successfully via SMTP.",
            sent_at=datetime.utcnow()
        )
        db.add(sent_log)
        db.commit()

        return {"status": "success", "message": f"Email successfully sent to {draft.recipient_email}."}

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Failed to send email to {draft.recipient_email}: {err_msg}")
        draft.status = "failed"
        draft.error_message = err_msg
        db.commit()
        return {"status": "error", "message": err_msg}


        sent_log = SentLog(
            user_id=user.id,
            job_id=job.id,
            recipient_email=draft.recipient_email,
            subject=draft.subject,
            body=draft.body,
            status="failed",
            details=err_msg,
            sent_at=datetime.utcnow()
        )
        db.add(sent_log)
        db.commit()
        return {"status": "error", "message": f"SMTP Error: {err_msg}"}



def approve_and_send_batch(db: Session, draft_ids: list[int], space_seconds: int = 10) -> Dict[str, Any]:
    """
    Approve and send a batch of drafts authorized by a single explicit user action ('Approve & Send Selected').
    Applies 10-second pacing between sends to prevent outbox flooding.
    """
    import threading

    def worker_send_batch():
        from backend.database import SessionLocal
        local_db = SessionLocal()
        try:
            for i, d_id in enumerate(draft_ids):
                if i > 0 and space_seconds > 0:
                    time.sleep(space_seconds)
                send_email_now(local_db, d_id)
        except Exception as ex:
            logger.error(f"Error in batch email send worker: {str(ex)}")
        finally:
            local_db.close()

    # If only 1 draft, send immediately synchronously
    if len(draft_ids) == 1:
        res = send_email_now(db, draft_ids[0])
        return {"status": "success", "sent_count": 1 if res["status"] == "success" else 0, "message": res["message"]}

    # Spawns thread initiated STRICTLY by the explicit user click action
    thread = threading.Thread(target=worker_send_batch, daemon=True)
    thread.start()

    return {
        "status": "success",
        "approved_count": len(draft_ids),
        "message": f"Approved {len(draft_ids)} drafts. Outgoing emails authorized and dispatches with {space_seconds}-second pacing."
    }

def process_queued_emails(db: Session) -> Dict[str, Any]:
    """
    Processes and sends pending/queued email drafts that are approved for sending.
    Applies per-user daily send limits and 10-second rate spacing.
    """
    queued_drafts = db.query(EmailDraft).filter(EmailDraft.status == "queued").all()
    sent_count = 0
    for draft in queued_drafts:
        res = send_email_now(db, draft.id)
        if res.get("status") == "success":
            sent_count += 1
        time.sleep(10)
    return {"processed": len(queued_drafts), "sent": sent_count}



