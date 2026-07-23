import pytest
from datetime import datetime, timedelta, timezone
from backend.services.password_validator import validate_strong_password
from backend.services.otp_service import generate_otp, verify_otp_code
from backend.models import OTPVerification

def test_strong_password_rules():
    # Weak passwords
    assert validate_strong_password("short")[0] is False
    assert validate_strong_password("nouppercase123!")[0] is False
    assert validate_strong_password("NOLOWERCASE123!")[0] is False
    assert validate_strong_password("NoNumbers!")[0] is False
    assert validate_strong_password("NoSpecial123")[0] is False

    # Valid strong password
    assert validate_strong_password("Strong#Pass2026")[0] is True

from backend.database import SessionLocal

def test_otp_generation_and_expiry():
    db = SessionLocal()
    try:
        email = "testuser@example.com"
        otp_code = generate_otp()
        assert len(otp_code) == 6
        assert otp_code.isdigit()

        # Valid 2-minute OTP
        otp_rec = OTPVerification(
            email=email,
            otp=otp_code,
            purpose="register",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
            is_verified=False
        )
        db.add(otp_rec)
        db.commit()

        ok, msg = verify_otp_code(db, email=email, otp_code=otp_code, purpose="register")
        assert ok is True
    finally:
        db.close()

def test_expired_otp():
    db = SessionLocal()
    try:
        email = "expired@example.com"
        otp_code = "654321"

        # Expired OTP (> 2 minutes old)
        otp_rec = OTPVerification(
            email=email,
            otp=otp_code,
            purpose="register",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            is_verified=False
        )
        db.add(otp_rec)
        db.commit()

        ok, msg = verify_otp_code(db, email=email, otp_code=otp_code, purpose="register")
        assert ok is False
        assert "expired" in msg.lower()
    finally:
        db.close()

