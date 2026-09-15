"""
Quick test: sends A test SMS + WhatsApp + Email using the current .env
settings. Run after filling in Twilio/SMTP keys:

    python test_notify.py

For every channel that is configured you'll get a "sent" status. If a
channel is blank it is skipped (logged only).
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from notifications import send_email, send_sms, send_whatsapp  # noqa: E402

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    phone = input("Your phone number with country code (e.g. +919043674143): ").strip()
    email = input("Your email (to receive the test email): ").strip()

    print("\n--- Sending test SMS ---")
    print(send_sms(phone, "LoomTrack test SMS - everything is working!"))

    print("\n--- Sending test WhatsApp ---")
    print(send_whatsapp(phone, "LoomTrack test WhatsApp - everything is working!"))

    print("\n--- Sending test Email ---")
    print(send_email(email, "LoomTrack test email", "LoomTrack test email - everything is working!"))
    print("\nDone. If a channel shows 'skipped', its keys in .env are blank.")