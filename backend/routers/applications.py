from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc


from backend.database import get_db
from backend.models import User, Job, EmailDraft, SentLog
from backend.schemas import (
    EmailDraftCreate, EmailDraftUpdate, EmailDraftOut,
    SentLogOut, AICoverNoteRequest, AICoverNoteResponse
)
from backend.routers.auth import get_current_user, get_current_user_optional
from backend.services.email_service import create_draft, send_email_now, approve_and_send_batch

from backend.services.ai_cover_note import generate_ai_cover_note

router = APIRouter(prefix="/api/applications", tags=["Applications"])

@router.post("/cover-note", response_model=AICoverNoteResponse)
def get_cover_note(
    req: AICoverNoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    job = db.query(Job).filter(Job.id == req.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    note = generate_ai_cover_note(db, current_user, job)
    return AICoverNoteResponse(
        job_id=job.id,
        job_title=job.title,
        company=job.company,
        cover_note=note
    )


@router.post("/draft", response_model=EmailDraftOut)
def create_email_draft(
    draft_in: EmailDraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    job = db.query(Job).filter(Job.id == draft_in.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    draft = create_draft(db, current_user, job, draft_in.recipient_email)
    
    return EmailDraftOut(
        id=draft.id,
        job_id=draft.job_id,
        recipient_email=draft.recipient_email,
        subject=draft.subject,
        body=draft.body,
        status=draft.status,
        send_after=draft.send_after,
        sent_at=draft.sent_at,
        error_message=draft.error_message,
        resume_name=draft.draft_resume_name,
        created_at=draft.created_at,
        job_title=job.title,
        company_name=job.company,
        role_category=job.role_category
    )


@router.get("/drafts", response_model=List[EmailDraftOut])
def get_pending_approval_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """
    Returns pending approvals inbox (drafts waiting for explicit user confirmation).
    Excludes sent emails which are moved to sent history logs.
    """
    drafts = db.query(EmailDraft).filter(
        EmailDraft.user_id == current_user.id,
        EmailDraft.status.in_(["draft", "failed"])
    ).order_by(desc(EmailDraft.created_at)).all()

    res = []
    for d in drafts:
        job = db.query(Job).filter(Job.id == d.job_id).first()
        res.append(
            EmailDraftOut(
                id=d.id,
                job_id=d.job_id,
                recipient_email=d.recipient_email,
                subject=d.subject,
                body=d.body,
                status=d.status,
                send_after=d.send_after,
                sent_at=d.sent_at,
                error_message=d.error_message,
                resume_name=d.draft_resume_name,
                created_at=d.created_at,
                job_title=job.title if job else None,
                company_name=job.company if job else None,
                role_category=job.role_category if job else None
            )
        )
    return res


@router.put("/drafts/{draft_id}", response_model=EmailDraftOut)
def update_draft(
    draft_id: int,
    draft_in: EmailDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    draft = db.query(EmailDraft).filter(
        EmailDraft.id == draft_id,
        EmailDraft.user_id == current_user.id
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")

    draft.subject = draft_in.subject
    draft.body = draft_in.body
    db.commit()
    db.refresh(draft)

    job = db.query(Job).filter(Job.id == draft.job_id).first()
    return EmailDraftOut(
        id=draft.id,
        job_id=draft.job_id,
        recipient_email=draft.recipient_email,
        subject=draft.subject,
        body=draft.body,
        status=draft.status,
        send_after=draft.send_after,
        sent_at=draft.sent_at,
        error_message=draft.error_message,
        resume_name=draft.draft_resume_name,
        created_at=draft.created_at,
        job_title=job.title if job else None,
        company_name=job.company if job else None,
        role_category=job.role_category if job else None
    )


@router.post("/drafts/{draft_id}/resume")
def upload_draft_resume(
    draft_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    import os
    from backend.config import settings

    draft = db.query(EmailDraft).filter(
        EmailDraft.id == draft_id,
        EmailDraft.user_id == current_user.id
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".pdf", ".docx", ".doc"}:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: PDF, DOCX, DOC.")

    save_filename = f"draft_{draft.id}_resume{ext}"
    save_path = settings.UPLOADS_DIR / save_filename

    with open(save_path, "wb") as buffer:
        buffer.write(file.file.read())

    draft.draft_resume_path = str(save_path)
    draft.draft_resume_name = file.filename
    db.commit()

    return {"status": "success", "message": f"Resume '{file.filename}' attached to draft.", "resume_name": file.filename}


@router.delete("/drafts/{draft_id}/resume")
def remove_draft_resume(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import os
    draft = db.query(EmailDraft).filter(
        EmailDraft.id == draft_id,
        EmailDraft.user_id == current_user.id
    ).first()

    if draft and draft.draft_resume_path:
        if os.path.exists(draft.draft_resume_path):
            try:
                os.remove(draft.draft_resume_path)
            except Exception:
                pass
        draft.draft_resume_path = None
        draft.draft_resume_name = None
        db.commit()

    return {"status": "success", "message": "Resume attachment removed from draft."}



@router.post("/drafts/{draft_id}/send")
def send_draft_now(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = db.query(EmailDraft).filter(
        EmailDraft.id == draft_id,
        EmailDraft.user_id == current_user.id
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")

    res = send_email_now(db, draft.id)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])

    return res


@router.post("/drafts/queue")
def queue_selected_drafts(
    draft_ids: List[int] = Body(..., embed=True),
    space_minutes: int = Body(2, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = queue_drafts(db, draft_ids, space_minutes=space_minutes)
    return res


@router.post("/drafts/approve-batch")
def approve_batch_drafts(
    draft_ids: List[int] = Body(..., embed=True),
    space_seconds: int = Body(120, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Approve and send a batch of drafts authorized by a single explicit user action ('Approve & Send Selected').
    Schedules sending with courteous pacing strictly initiated by this user action.
    """
    from backend.services.email_service import approve_and_send_batch
    res = approve_and_send_batch(db, draft_ids, space_seconds=space_seconds)
    return res



@router.delete("/drafts/{draft_id}")
def delete_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = db.query(EmailDraft).filter(
        EmailDraft.id == draft_id,
        EmailDraft.user_id == current_user.id
    ).first()

    if draft:
        db.delete(draft)
        db.commit()

    return {"status": "success", "message": "Draft deleted."}


@router.get("/logs", response_model=List[SentLogOut])
def get_sent_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logs = db.query(SentLog).filter(
        SentLog.user_id == current_user.id
    ).order_by(desc(SentLog.sent_at)).all()

    res = []
    for l in logs:
        job = db.query(Job).filter(Job.id == l.job_id).first()
        res.append(
            SentLogOut(
                id=l.id,
                job_id=l.job_id,
                recipient_email=l.recipient_email,
                subject=l.subject,
                body=l.body,
                status=l.status,
                details=l.details,
                sent_at=l.sent_at,
                job_title=job.title if job else None,
                company_name=job.company if job else None
            )
        )
    return res
