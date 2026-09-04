"""
Dispatch functions for SMS, WhatsApp, and Email reminders.

Each function degrades gracefully to a console log if its provider isn't
configured, so the scheduler can be run and tested locally with zero
external services set up.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("notifications")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "maintenance-alerts@example.com")

_twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        from twilio.rest import Client

        _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except ImportError:
        logger.warning("twilio package not installed; SMS/WhatsApp will be logged only")


def send_sms(to_phone: str, message: str) -> dict:
    if not _twilio_client or not TWILIO_SMS_FROM:
        logger.info(f"[SMS - not configured, logging only] to={to_phone}: {message}")
        return {"status": "skipped", "reason": "twilio not configured"}
    try:
        msg = _twilio_client.messages.create(body=message, from_=TWILIO_SMS_FROM, to=to_phone)
        return {"status": "sent", "sid": msg.sid}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"SMS failed to {to_phone}: {exc}")
        return {"status": "failed", "error": str(exc)}


def send_whatsapp(to_phone: str, message: str) -> dict:
    if not _twilio_client or not TWILIO_WHATSAPP_FROM:
        logger.info(f"[WhatsApp - not configured, logging only] to={to_phone}: {message}")
        return {"status": "skipped", "reason": "twilio not configured"}
    try:
        msg = _twilio_client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone,
        )
        return {"status": "sent", "sid": msg.sid}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"WhatsApp failed to {to_phone}: {exc}")
        return {"status": "failed", "error": str(exc)}


def send_email(to_email: str, subject: str, message: str) -> dict:
    if not SMTP_HOST or not SMTP_USER:
        logger.info(f"[Email - not configured, logging only] to={to_email} subject={subject}: {message}")
        return {"status": "skipped", "reason": "smtp not configured"}
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        return {"status": "sent"}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Email failed to {to_email}: {exc}")
        return {"status": "failed", "error": str(exc)}
