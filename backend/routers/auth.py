from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import bcrypt
from backend.database import get_db
from backend.config import settings
from backend.models import User, UserSettings, RoleTemplate
from backend.schemas import UserCreate, UserOut, Token, UserLogin

router = APIRouter(prefix="/api/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain text password against bcrypt hashed password safely."""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hash_bytes = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hashes password with bcrypt safely enforcing 72-byte limit."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")



def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/register", response_model=UserOut, status_code=201)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered.")

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        full_name=user_in.full_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Initialize default settings
    user_settings = UserSettings(
        user_id=new_user.id,
        adzuna_app_id=settings.ADZUNA_APP_ID,
        adzuna_app_key=settings.ADZUNA_APP_KEY,
        gemini_api_key=settings.GEMINI_API_KEY,
        smtp_server=settings.SMTP_SERVER,
        smtp_port=settings.SMTP_PORT,
        smtp_email=settings.SMTP_EMAIL or new_user.email,
        smtp_password=settings.SMTP_PASSWORD
    )
    db.add(user_settings)

    # Initialize default templates for Data Analyst & Data Scientist
    da_template = RoleTemplate(
        user_id=new_user.id,
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
        user_id=new_user.id,
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

    return new_user


@router.post("/login", response_model=Token)
def login_user(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password.")
        
    token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password.")
        
    token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
