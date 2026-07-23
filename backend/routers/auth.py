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
        
    return user

oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)) -> User:
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email: str = payload.get("sub")
            if email:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    return user
        except Exception:
            pass

    # Fallback to demo user if not logged in
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
    return demo_user



from backend.schemas import UserCreate, UserOut, Token, UserLogin, OTPRequest, OTPRegisterVerify, OTPPasswordReset
from backend.services.password_validator import validate_strong_password
from backend.services.otp_service import create_and_send_otp, verify_otp_code

@router.post("/send-register-otp")
def send_register_otp(user_in: UserCreate, db: Session = Depends(get_db)):
    """Validates strong password rules & sends 2-minute OTP to email before registering."""
    clean_email = user_in.email.strip().lower() if user_in.email else ""
    existing = db.query(User).filter(func.lower(User.email) == clean_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="This email address is already registered.")


    valid, err_msg = validate_strong_password(user_in.password)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    create_and_send_otp(db, email=clean_email, purpose="register")
    return {"message": "6-digit OTP sent to your email. Valid for 2 minutes."}


@router.post("/verify-register-otp", response_model=Token)
def verify_register_otp(data: OTPRegisterVerify, db: Session = Depends(get_db)):
    """Verifies 2-minute OTP & creates/activates user account upon successful verification."""
    valid_pw, err_msg = validate_strong_password(data.password)
    if not valid_pw:
        raise HTTPException(status_code=400, detail=err_msg)

    verified, otp_msg = verify_otp_code(db, email=data.email, otp_code=data.otp, purpose="register")
    if not verified:
        raise HTTPException(status_code=400, detail=otp_msg)

    existing = db.query(User).filter(User.email == data.email).first()
    hashed_pw = get_password_hash(data.password)

    if existing:
        user = existing
        user.hashed_password = hashed_pw
        user.full_name = data.full_name
        db.commit()
    else:
        user = User(
            email=data.email,
            hashed_password=hashed_pw,
            full_name=data.full_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Ensure default settings exist
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not user_settings:
        user_settings = UserSettings(
            user_id=user.id,
            adzuna_app_id=settings.ADZUNA_APP_ID,
            adzuna_app_key=settings.ADZUNA_APP_KEY,
            gemini_api_key=settings.GEMINI_API_KEY,
            smtp_server=settings.SMTP_SERVER,
            smtp_port=settings.SMTP_PORT,
            smtp_email=settings.SMTP_EMAIL or user.email,
            smtp_password=settings.SMTP_PASSWORD
        )
        db.add(user_settings)
        db.commit()

    token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/forgot-password/request-otp")

def forgot_password_request_otp(data: OTPRequest, db: Session = Depends(get_db)):
    """Verifies registered user email & sends 2-minute password reset OTP."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account with this email address was not found.")

    create_and_send_otp(db, email=data.email, purpose="forgot_password")
    return {"message": "Password reset OTP sent to your email. Valid for 2 minutes."}

@router.post("/forgot-password/reset")
def forgot_password_reset(data: OTPPasswordReset, db: Session = Depends(get_db)):
    """Verifies 2-minute OTP & resets user password with strong password rules."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account with this email address was not found.")

    valid_pw, err_msg = validate_strong_password(data.new_password)
    if not valid_pw:
        raise HTTPException(status_code=400, detail=err_msg)

    verified, otp_msg = verify_otp_code(db, email=data.email, otp_code=data.otp, purpose="forgot_password")
    if not verified:
        raise HTTPException(status_code=400, detail=otp_msg)

    user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Password reset successful! You can now log in with your new password."}

@router.post("/register", response_model=UserOut, status_code=201)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered.")

    valid, err_msg = validate_strong_password(user_in.password)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        full_name=user_in.full_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

from sqlalchemy import func

@router.post("/login", response_model=Token)
def login_user(user_in: UserLogin, db: Session = Depends(get_db)):
    clean_email = user_in.email.strip().lower() if user_in.email else ""
    user = db.query(User).filter(func.lower(User.email) == clean_email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password.")
        
    token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    clean_username = form_data.username.strip().lower() if form_data.username else ""
    user = db.query(User).filter(func.lower(User.email) == clean_username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password.")
        
    token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}



@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
