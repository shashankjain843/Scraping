import sys
from pathlib import Path

# Automatically add project root to python path so app runs from any folder
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from backend.config import settings

from backend.database import Base, engine, SessionLocal
from backend.models import User, UserSettings, Job, RoleTemplate
from backend.routers.auth import router as auth_router, get_password_hash
from backend.routers.jobs import router as jobs_router
from backend.routers.templates import router as templates_router
from backend.routers.applications import router as applications_router
from backend.routers.settings import router as settings_router
from backend.routers.assistant import router as assistant_router
from backend.services.adzuna_service import fetch_adzuna_jobs
from backend.services.email_service import process_queued_emails




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# Initialize APScheduler for background rate-spaced email sending & periodic Adzuna job polling
scheduler = BackgroundScheduler()

def scheduled_job_fetch():
    """Background task to poll Adzuna API periodically respecting rate limits."""
    logger.info("Executing scheduled Adzuna job fetch...")
    db = SessionLocal()
    try:
        # Fetch for users who configured Adzuna credentials or system default
        fetch_adzuna_jobs(db)
    except Exception as e:
        logger.error(f"Scheduled job fetch error: {str(e)}")
    finally:
        db.close()

def scheduled_email_queue_processor():
    """Background task to process queued email drafts with rate spacing."""
    db = SessionLocal()
    try:
        process_queued_emails(db)
    except Exception as e:
        logger.error(f"Scheduled email queue processor error: {str(e)}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    Base.metadata.create_all(bind=engine)
    seed_demo_data()

    # Start background scheduler ONLY for Feature 1 (Adzuna job fetching)
    scheduler.add_job(scheduled_job_fetch, 'interval', minutes=15, id="adzuna_fetch_job", replace_existing=True)
    scheduler.start()
    logger.info("APScheduler started strictly for Feature 1 job fetching (never for email sending).")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Application shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(templates_router)
app.include_router(applications_router)
app.include_router(settings_router)
app.include_router(assistant_router)

# Mount uploads directory
app.mount("/uploads", StaticFiles(directory=settings.UPLOADS_DIR), name="uploads")

# Mount frontend dist static files if built
frontend_dist = settings.BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def read_root():
        return {"message": "Fresher Job Application Platform API is running", "docs": "/docs"}


def seed_demo_data():
    """Seeds initial demo user and realistic initial job listings if database is empty."""

    db = SessionLocal()
    try:
        # Create default demo user
        demo_user = db.query(User).filter(User.email == "user@example.com").first()
        if not demo_user:
            demo_user = User(
                email="user@example.com",
                hashed_password=get_password_hash("password123"),
                full_name="Shashank Jain"
            )
            db.add(demo_user)
            db.commit()
            db.refresh(demo_user)

            # Add default settings
            st = UserSettings(
                user_id=demo_user.id,
                adzuna_app_id=settings.ADZUNA_APP_ID,
                adzuna_app_key=settings.ADZUNA_APP_KEY,
                gemini_api_key=settings.GEMINI_API_KEY,
                smtp_server=settings.SMTP_SERVER,
                smtp_port=settings.SMTP_PORT,
                smtp_email=settings.SMTP_EMAIL or demo_user.email,
                smtp_password=settings.SMTP_PASSWORD
            )
            db.add(st)

            # Default templates
            da_template = RoleTemplate(
                user_id=demo_user.id,
                role_category="data_analyst",
                subject_template="Application for {{job_title}} - {{company}}",
                body_template=(
                    "Dear Hiring Manager,\n\n"
                    "I am writing to express my enthusiastic interest in the {{job_title}} role at {{company}} in {{city}}.\n\n"
                    "My background includes hands-on experience with SQL query optimization, Python data analytics libraries (pandas, numpy), "
                    "and interactive dashboard visualization tools (Power BI / Tableau). I am eager to leverage data insights to support "
                    "{{company}}'s strategic goals.\n\n"
                    "Please find my resume attached for your consideration. I look forward to the opportunity to discuss how my skill set "
                    "aligns with your team's needs.\n\n"
                    "Sincerely,\n"
                    "{{user_name}}\n"
                    "{{user_email}}"
                )
            )
            ds_template = RoleTemplate(
                user_id=demo_user.id,
                role_category="data_scientist",
                subject_template="Application for {{job_title}} Position - {{company}}",
                body_template=(
                    "Dear Hiring Team,\n\n"
                    "I am applying for the {{job_title}} position at {{company}} in {{city}}.\n\n"
                    "With a strong foundation in machine learning algorithms, statistical analysis, Python data science frameworks, "
                    "and SQL database management, I am confident in my ability to build predictive models and deliver actionable insights "
                    "for {{company}}.\n\n"
                    "Attached is my resume for your review. Thank you for your time and consideration.\n\n"
                    "Best regards,\n"
                    "{{user_name}}\n"
                    "{{user_email}}"
                )
            )
            db.add(da_template)
            db.add(ds_template)
            db.commit()

        # Seed sample job listings if empty
        if db.query(Job).count() == 0:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            sample_jobs = [
                Job(
                    source="adzuna",
                    source_job_id="sample_001",
                    title="Junior Data Analyst",
                    company="Analytics Analytics Pvt Ltd",
                    location="Gurgaon, Haryana",
                    city="Gurgaon",
                    description="We are hiring a Junior Data Analyst with 0-1 years experience in SQL, Python, and Power BI dashboard creation. Responsible for ETL pipelines, data validation, and automated reporting.",
                    apply_url="https://www.adzuna.in/details/sample_001",
                    salary_min=450000,
                    salary_max=650000,
                    role_category="data_analyst",
                    bucket_0_1=True,
                    bucket_1_3=False,
                    created_at=now - timedelta(hours=2)
                ),
                Job(
                    source="adzuna",
                    source_job_id="sample_002",
                    title="Data Scientist - Fresher",
                    company="AI Solutions India",
                    location="Bengaluru, Karnataka",
                    city="Bangalore",
                    description="Seeking Entry Level Data Scientist. Requirements: Strong Python, Pandas, Scikit-Learn, and SQL knowledge. Experience: 0-1 years or fresh graduates with strong project portfolios.",
                    apply_url="https://www.adzuna.in/details/sample_002",
                    salary_min=700000,
                    salary_max=950000,
                    role_category="data_scientist",
                    bucket_0_1=True,
                    bucket_1_3=False,
                    created_at=now - timedelta(hours=5)
                ),
                Job(
                    source="adzuna",
                    source_job_id="sample_003",
                    title="Data Analyst (1-2 Years Experience)",
                    company="TechCorp Noida",
                    location="Noida, Uttar Pradesh",
                    city="Noida",
                    description="Immediate requirement for Data Analyst with 1-2 years experience. Must be proficient in SQL queries, Excel macros, and Tableau reporting.",
                    apply_url="https://www.adzuna.in/details/sample_003",
                    salary_min=600000,
                    salary_max=850000,
                    role_category="data_analyst",
                    bucket_0_1=True,
                    bucket_1_3=True,
                    created_at=now - timedelta(hours=12)
                ),
                Job(
                    source="adzuna",
                    source_job_id="sample_004",
                    title="Associate Data Scientist (1-3 yrs)",
                    company="Innovate AI Hyderabad",
                    location="Hyderabad, Telangana",
                    city="Hyderabad",
                    description="Looking for an Associate Data Scientist with 1-3 years experience in NLP, machine learning models, PyTorch, and SQL databases.",
                    apply_url="https://www.adzuna.in/details/sample_004",
                    salary_min=900000,
                    salary_max=1300000,
                    role_category="data_scientist",
                    bucket_0_1=False,
                    bucket_1_3=True,
                    created_at=now - timedelta(days=1)
                ),
                Job(
                    source="adzuna",
                    source_job_id="sample_005",
                    title="Data Analyst - Business Intelligence",
                    company="FinTech Pune",
                    location="Pune, Maharashtra",
                    city="Pune",
                    description="Data Analyst role for freshers and 0-1 year experience candidates. Skills required: MySQL, Python, Data Visualization, Excel.",
                    apply_url="https://www.adzuna.in/details/sample_005",
                    salary_min=500000,
                    salary_max=700000,
                    role_category="data_analyst",
                    bucket_0_1=True,
                    bucket_1_3=False,
                    created_at=now - timedelta(days=1, hours=4)
                ),
                Job(
                    source="adzuna",
                    source_job_id="sample_006",
                    title="Data Scientist - Machine Learning",
                    company="Jaipur Analytics Hub",
                    location="Jaipur, Rajasthan",
                    city="Jaipur",
                    description="Hiring Data Scientist with 1-2 years hands-on experience building ML classifiers, regression models, and exploratory data analysis.",
                    apply_url="https://www.adzuna.in/details/sample_006",
                    salary_min=650000,
                    salary_max=900000,
                    role_category="data_scientist",
                    bucket_0_1=True,
                    bucket_1_3=True,
                    created_at=now - timedelta(days=2)
                )
            ]
            db.add_all(sample_jobs)
            db.commit()
            logger.info("Seeded initial demo job listings.")
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Fresher Job Application Platform API is running", "docs": "/docs"}
