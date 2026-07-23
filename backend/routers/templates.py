import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import settings
from backend.models import RoleTemplate, User
from backend.schemas import RoleTemplateOut, RoleTemplateUpdate
from backend.routers.auth import get_current_user, get_current_user_optional
from backend.services.email_service import DEFAULT_TEMPLATES, render_email_template

router = APIRouter(prefix="/api/templates", tags=["Role Templates"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

@router.get("", response_model=List[RoleTemplateOut])
def get_user_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    templates = db.query(RoleTemplate).filter(RoleTemplate.user_id == current_user.id).all()
    
    # Format has_resume flag
    res = []
    for t in templates:
        has_res = bool(t.resume_file_path and os.path.exists(t.resume_file_path))
        res.append(
            RoleTemplateOut(
                id=t.id,
                role_category=t.role_category,
                subject_template=t.subject_template,
                body_template=t.body_template,
                resume_file_name=t.resume_file_name if has_res else None,
                has_resume=has_res,
                updated_at=t.updated_at
            )
        )
    return res


@router.put("/{role_category}", response_model=RoleTemplateOut)
def update_template(
    role_category: str,
    template_in: RoleTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if role_category not in ("data_analyst", "data_scientist"):
        raise HTTPException(status_code=400, detail="Invalid role category.")

    template = db.query(RoleTemplate).filter(
        RoleTemplate.user_id == current_user.id,
        RoleTemplate.role_category == role_category
    ).first()

    if not template:
        template = RoleTemplate(
            user_id=current_user.id,
            role_category=role_category,
            subject_template=template_in.subject_template,
            body_template=template_in.body_template
        )
        db.add(template)
    else:
        template.subject_template = template_in.subject_template
        template.body_template = template_in.body_template

    db.commit()
    db.refresh(template)

    has_res = bool(template.resume_file_path and os.path.exists(template.resume_file_path))
    return RoleTemplateOut(
        id=template.id,
        role_category=template.role_category,
        subject_template=template.subject_template,
        body_template=template.body_template,
        resume_file_name=template.resume_file_name if has_res else None,
        has_resume=has_res,
        updated_at=template.updated_at
    )


@router.post("/{role_category}/resume")
def upload_resume(
    role_category: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if role_category not in ("data_analyst", "data_scientist"):
        raise HTTPException(status_code=400, detail="Invalid role category.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: PDF, DOCX, DOC.")

    template = db.query(RoleTemplate).filter(
        RoleTemplate.user_id == current_user.id,
        RoleTemplate.role_category == role_category
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found.")

    # Save file to uploads folder
    save_filename = f"user_{current_user.id}_{role_category}{ext}"
    save_path = settings.UPLOADS_DIR / save_filename

    with open(save_path, "wb") as buffer:
        buffer.write(file.file.read())

    template.resume_file_path = str(save_path)
    template.resume_file_name = file.filename
    db.commit()

    return {"status": "success", "message": f"Resume attached for {role_category}.", "file_name": file.filename}


@router.delete("/{role_category}/resume")
def remove_resume(
    role_category: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    template = db.query(RoleTemplate).filter(
        RoleTemplate.user_id == current_user.id,
        RoleTemplate.role_category == role_category
    ).first()

    if template and template.resume_file_path:
        if os.path.exists(template.resume_file_path):
            try:
                os.remove(template.resume_file_path)
            except Exception:
                pass
        template.resume_file_path = None
        template.resume_file_name = None
        db.commit()

    return {"status": "success", "message": "Resume removed."}
