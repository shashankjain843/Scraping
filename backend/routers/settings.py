from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, UserSettings
from backend.schemas import UserSettingsOut, UserSettingsUpdate
from backend.routers.auth import get_current_user_optional

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("", response_model=UserSettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):

    st = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    if not st:
        st = UserSettings(user_id=current_user.id)
        db.add(st)
        db.commit()
        db.refresh(st)

    return UserSettingsOut(
        adzuna_app_id=st.adzuna_app_id or "",
        adzuna_app_key=st.adzuna_app_key or "",
        gemini_api_key=st.gemini_api_key or "",
        smtp_server=st.smtp_server or "smtp.gmail.com",
        smtp_port=st.smtp_port or 587,
        smtp_email=st.smtp_email or "",
        smtp_password_set=bool(st.smtp_password),
        phone_number=st.phone_number or "",
        linkedin_url=st.linkedin_url or "",
        daily_send_limit=st.daily_send_limit if st.daily_send_limit is not None else 30,
        tos_accepted=bool(st.tos_accepted)
    )


@router.put("", response_model=UserSettingsOut)
def update_settings(
    settings_in: UserSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):

    st = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    if not st:
        st = UserSettings(user_id=current_user.id)
        db.add(st)

    if settings_in.adzuna_app_id is not None:
        st.adzuna_app_id = settings_in.adzuna_app_id
    if settings_in.adzuna_app_key is not None:
        st.adzuna_app_key = settings_in.adzuna_app_key
    if settings_in.gemini_api_key is not None:
        st.gemini_api_key = settings_in.gemini_api_key
    if settings_in.smtp_server is not None:
        st.smtp_server = settings_in.smtp_server
    if settings_in.smtp_port is not None:
        st.smtp_port = settings_in.smtp_port
    if settings_in.smtp_email is not None:
        st.smtp_email = settings_in.smtp_email
    if settings_in.smtp_password is not None and settings_in.smtp_password.strip() != "":
        st.smtp_password = settings_in.smtp_password
    if settings_in.phone_number is not None:
        st.phone_number = settings_in.phone_number
    if settings_in.linkedin_url is not None:
        st.linkedin_url = settings_in.linkedin_url
    if settings_in.daily_send_limit is not None:
        st.daily_send_limit = settings_in.daily_send_limit
    if settings_in.tos_accepted is not None:
        st.tos_accepted = settings_in.tos_accepted

    db.commit()
    db.refresh(st)

    return UserSettingsOut(
        adzuna_app_id=st.adzuna_app_id or "",
        adzuna_app_key=st.adzuna_app_key or "",
        gemini_api_key=st.gemini_api_key or "",
        smtp_server=st.smtp_server or "smtp.gmail.com",
        smtp_port=st.smtp_port or 587,
        smtp_email=st.smtp_email or "",
        smtp_password_set=bool(st.smtp_password),
        phone_number=st.phone_number or "",
        linkedin_url=st.linkedin_url or "",
        daily_send_limit=st.daily_send_limit if st.daily_send_limit is not None else 30,
        tos_accepted=bool(st.tos_accepted)
    )

