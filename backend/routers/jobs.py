from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import or_, and_, desc
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Job, User, UserSettings
from backend.schemas import JobOut
from backend.routers.auth import get_current_user
from backend.services.adzuna_service import fetch_adzuna_jobs

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

@router.get("", response_model=List[JobOut])
def list_jobs(
    roles: Optional[List[str]] = Query(None, description="Roles: data_analyst, data_scientist"),
    cities: Optional[List[str]] = Query(None, description="Cities e.g. Gurgaon, Bangalore, Noida"),
    exp_buckets: Optional[List[str]] = Query(None, description="Experience buckets: 0-1, 1-3"),
    q: Optional[str] = Query(None, description="Keyword search query"),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Job)

    # Filter by role categories if provided
    if roles:
        query = query.filter(Job.role_category.in_(roles))

    # Filter by cities if provided
    if cities:
        query = query.filter(Job.city.in_(cities))

    # Filter by experience buckets if provided
    if exp_buckets:
        exp_conditions = []
        if "0-1" in exp_buckets:
            exp_conditions.append(Job.bucket_0_1 == True)
        if "1-3" in exp_buckets:
            exp_conditions.append(Job.bucket_1_3 == True)
        if exp_conditions:
            query = query.filter(or_(*exp_conditions))

    # Filter by search keyword if provided
    if q:
        search_fmt = f"%{q}%"
        query = query.filter(
            or_(
                Job.title.ilike(search_fmt),
                Job.company.ilike(search_fmt),
                Job.description.ilike(search_fmt)
            )
        )

    # Sort by created_at date (most recently posted first)
    query = query.order_by(desc(Job.created_at), desc(Job.id))

    jobs = query.offset(offset).limit(limit).all()
    return jobs


@router.post("/fetch")
def trigger_fetch_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually triggers Adzuna API fetch using user's configured app_id / app_key.
    Respects Adzuna rate limits and deduplicates entries.
    """
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    app_id = user_settings.adzuna_app_id if user_settings else ""
    app_key = user_settings.adzuna_app_key if user_settings else ""

    result = fetch_adzuna_jobs(db, app_id=app_id, app_key=app_key)
    if result["status"] == "rate_limited":
        raise HTTPException(status_code=429, detail=result["message"])
    elif result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result
