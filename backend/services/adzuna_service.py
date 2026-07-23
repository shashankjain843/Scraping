import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import requests
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import Job, AdzunaQuotaLog
from backend.services.job_parser import parse_city, parse_experience, parse_role_category

logger = logging.getLogger("adzuna_service")

# Search target query terms for Adzuna API
ROLES_TO_FETCH = ["Data Analyst", "Data Scientist"]

def check_adzuna_rate_limit(db: Session) -> bool:
    """
    Ensures we do not exceed Adzuna rate limits:
    - Max 25 calls per minute
    - Max 250 calls per day
    """
    now = datetime.utcnow()
    one_minute_ago = now - timedelta(minutes=1)
    today_start = datetime.combine(date.today(), datetime.min.time())

    # Count calls in last 1 minute
    calls_last_min = db.query(AdzunaQuotaLog).filter(AdzunaQuotaLog.fetched_at >= one_minute_ago).count()
    if calls_last_min >= settings.ADZUNA_CALLS_PER_MINUTE_LIMIT:
        logger.warning(f"Adzuna rate limit reached: {calls_last_min} calls in last minute.")
        return False

    # Count calls today
    calls_today = db.query(AdzunaQuotaLog).filter(AdzunaQuotaLog.fetched_at >= today_start).count()
    if calls_today >= settings.ADZUNA_CALLS_PER_DAY_LIMIT:
        logger.warning(f"Adzuna daily rate limit reached: {calls_today} calls today.")
        return False

    return True


def fetch_adzuna_jobs(db: Session, app_id: str = "", app_key: str = "", roles: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Fetches jobs from official Adzuna REST API for India (/jobs/in/search).
    Enforces deduplication by (source, source_job_id) and strict target city/role matching.
    """
    app_id = app_id or settings.ADZUNA_APP_ID
    app_key = app_key or settings.ADZUNA_APP_KEY

    if not app_id or not app_key:
        logger.warning("Adzuna App ID or App Key missing. Cannot fetch jobs.")
        return {"status": "error", "message": "Adzuna API credentials missing.", "new_jobs": 0}

    if not check_adzuna_rate_limit(db):
        return {"status": "rate_limited", "message": "Adzuna API rate limit reached. Try again later.", "new_jobs": 0}

    roles_to_fetch = roles or ROLES_TO_FETCH
    total_new_jobs = 0
    errors = []

    for role_term in roles_to_fetch:
        if not check_adzuna_rate_limit(db):
            break

        # Query page 1 (most recent 20-50 jobs per role)
        url = f"https://api.adzuna.com/v1/api/jobs/in/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 50,
            "what": role_term,
            "content-type": "application/json",
            "sort_by": "date" # sort by most recently posted
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            
            # Log quota usage
            quota_entry = AdzunaQuotaLog(endpoint="/jobs/in/search", records_count=0)
            db.add(quota_entry)
            db.commit()

            if response.status_code != 200:
                err_msg = f"Adzuna API HTTP {response.status_code}: {response.text}"
                logger.error(err_msg)
                errors.append(err_msg)
                continue

            data = response.json()
            results = data.get("results", [])
            quota_entry.records_count = len(results)
            db.commit()

            for item in results:
                source_job_id = str(item.get("id"))
                if not source_job_id:
                    continue

                # Deduplication check
                existing = db.query(Job).filter(Job.source == "adzuna", Job.source_job_id == source_job_id).first()
                if existing:
                    continue

                # Extract location and check city matching
                location_data = item.get("location", {})
                display_location = location_data.get("display_name", "") or ""
                canonical_city = parse_city(display_location)
                
                # If Adzuna display_name doesn't match canonical city, check area list
                if not canonical_city:
                    area_list = location_data.get("area", [])
                    for area_name in area_list:
                        canonical_city = parse_city(area_name)
                        if canonical_city:
                            break

                # Ignore jobs outside target cities
                if not canonical_city:
                    continue

                # Extract role category
                raw_title = item.get("title", "")
                raw_desc = item.get("description", "")
                role_cat = parse_role_category(raw_title, raw_desc)
                if not role_cat:
                    continue

                # Extract experience buckets
                b0_1, b1_3 = parse_experience(raw_title, raw_desc)

                # Parse created date
                created_str = item.get("created")
                created_dt = datetime.utcnow()
                if created_str:
                    try:
                        # Adzuna format: "2026-07-23T10:30:00Z"
                        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pass

                company_name = item.get("company", {}).get("display_name", "Company Confidential")
                apply_url = item.get("redirect_url") or item.get("url") or ""

                new_job = Job(
                    source="adzuna",
                    source_job_id=source_job_id,
                    title=raw_title,
                    company=company_name,
                    location=display_location,
                    city=canonical_city,
                    description=raw_desc,
                    apply_url=apply_url,
                    salary_min=item.get("salary_min"),
                    salary_max=item.get("salary_max"),
                    role_category=role_cat,
                    bucket_0_1=b0_1,
                    bucket_1_3=b1_3,
                    created_at=created_dt,
                    fetched_at=datetime.utcnow()
                )
                db.add(new_job)
                total_new_jobs += 1

            db.commit()

        except Exception as e:
            logger.error(f"Error fetching Adzuna jobs for {role_term}: {str(e)}")
            errors.append(str(e))

    return {
        "status": "success" if not errors else "partial_error",
        "new_jobs": total_new_jobs,
        "errors": errors
    }
