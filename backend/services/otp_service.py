import random
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.models import OTPVerification
from backend.config import settings

def generate_otp() -> str:
    """Generates a 6-digit numeric OTP code."""
    return f"{random.randint(100000, 999999)}"

def send_otp_email(email: str, otp: str, purpose: str) -> bool:
    """
    Sends 6-digit OTP code to the recipient email via configured SMTP server.
    Tries SMTP_SSL (port 465) first, falls back to STARTTLS (port 587).
    """
    subject = "Your Verification OTP Code - JobAssist AI"
    if purpose == "register":
        body_intro = "Thank you for registering with JobAssist AI. Use the OTP below to complete your registration:"
    else:
        body_intro = "You requested to reset your password on JobAssist AI. Use the OTP below to reset your password:"

    body = (
        f"Hi,\n\n"
        f"{body_intro}\n\n"
        f"OTP CODE: {otp}\n\n"
        f"Note: This OTP is valid for exactly 2 minutes. Do not share it with anyone.\n\n"
        f"Regards,\n"
        f"JobAssist AI Security Team"
    )

    print(f"\n==========================================")
    print(f"🔒 [OTP GENERATED] Email: {email} | Purpose: {purpose} | OTP: {otp} | Expiry: 2 mins")
    print(f"==========================================\n")

    # Attempt SMTP delivery if configured
    if not (settings.SMTP_SERVER and settings.SMTP_EMAIL and settings.SMTP_PASSWORD):
        print("⚠️ SMTP not configured — OTP only printed to console.")
        return True

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Try SSL on port 465 first (most reliable on cloud/Render)
    try:
        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.SMTP_SERVER, 465, context=context, timeout=15) as server:
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ OTP email sent via SSL to {email}")
        return True
    except Exception as ssl_err:
        print(f"⚠️ SSL send failed: {ssl_err} — trying STARTTLS...")

    # Fallback: STARTTLS on port 587
    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ OTP email sent via STARTTLS to {email}")
        return True
    except Exception as tls_err:
        print(f"❌ STARTTLS send also failed: {tls_err}")
        return False


def create_and_send_otp(db: Session, email: str, purpose: str) -> str:
    """
    Creates a new 2-minute expiring OTP record in DB and sends email.
    """
    # Delete old unverified OTPs for this email & purpose
    db.query(OTPVerification).filter(
        OTPVerification.email == email,
        OTPVerification.purpose == purpose
    ).delete()
    db.commit()

    otp_code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)

    otp_rec = OTPVerification(
        email=email,
        otp=otp_code,
        purpose=purpose,
        expires_at=expires_at,
        is_verified=False
    )
    db.add(otp_rec)
    db.commit()

    # Send email in background thread — don't block the API response
    thread = threading.Thread(target=send_otp_email, args=(email, otp_code, purpose), daemon=True)
    thread.start()
    return otp_code

def verify_otp_code(db: Session, email: str, otp_code: str, purpose: str) -> tuple[bool, str]:
    """
    Verifies that the OTP code matches, belongs to the email, and is unexpired (within 2 minutes).
    """
    otp_rec = db.query(OTPVerification).filter(
        OTPVerification.email == email,
        OTPVerification.otp == otp_code,
        OTPVerification.purpose == purpose
    ).order_by(OTPVerification.id.desc()).first()

    if not otp_rec:
        return False, "Invalid OTP code. Please check and try again."

    if datetime.now(timezone.utc) > otp_rec.expires_at.replace(tzinfo=timezone.utc):
        return False, "OTP has expired (validity was 2 minutes). Please request a new OTP."

    # Mark as verified
    otp_rec.is_verified = True
    db.commit()
    return True, "OTP successfully verified!"
