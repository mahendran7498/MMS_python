"""
Machine Maintenance Management System - Scheduler Service.

Runs as a daily cron-style job (via APScheduler) that:
  1. Checks the backend for oil-change records due today/overdue.
  2. Checks the backend for maintenance records due today/overdue.
  3. Sends SMS + WhatsApp + Email reminders to assigned employees and the Owner.
  4. Marks reminders as sent back on the backend so they aren't re-sent daily.
  5. Logs a Notification record on the backend for the in-app notification center.

Run once immediately with:  python scheduler.py --now
Run as a persistent daily scheduler with:  python scheduler.py
"""

import os
import sys
import logging
import argparse
from datetime import datetime

import requests
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler

from notifications import send_sms, send_whatsapp, send_email

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000/api")
SCHEDULER_API_KEY = os.getenv("SCHEDULER_API_KEY", "")
OWNER_EMAIL = os.getenv("OWNER_EMAIL")
OWNER_PHONE = os.getenv("OWNER_PHONE")

HEADERS = {"x-scheduler-key": SCHEDULER_API_KEY, "Content-Type": "application/json"}


def api_get(path: str, params: dict | None = None):
    resp = requests.get(f"{API_BASE_URL}{path}", headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_patch(path: str, json: dict | None = None):
    resp = requests.patch(f"{API_BASE_URL}{path}", headers=HEADERS, json=json or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, json: dict):
    resp = requests.post(f"{API_BASE_URL}{path}", headers=HEADERS, json=json, timeout=30)
    resp.raise_for_status()
    return resp.json()


def process_oil_changes():
    """The single most important scheduled job per the product spec:
    Oil Change Date + 6 months -> automatic reminder on the due date."""
    logger.info("Checking oil changes due today...")
    due_records = api_get("/oil-changes/due/today").get("data", [])
    logger.info(f"Found {len(due_records)} oil change reminder(s) due")

    for record in due_records:
        machine = record.get("machine") or {}
        machine_name = machine.get("machineName", "Unknown machine")
        machine_number = machine.get("machineNumber", "")
        assigned_employees = machine.get("assignedEmployees", []) or []

        message = (
            f"Machine: {machine_name} ({machine_number})\n"
            f"Oil Change Due Today\n"
            f"Please replace the oil immediately."
        )

        recipients_payload = []

        # Notify every employee assigned to this machine
        for emp in assigned_employees:
            phone = emp.get("phoneNumber")
            email = emp.get("email")
            if phone:
                sms_result = send_sms(phone, message)
                wa_result = send_whatsapp(phone, message)
                recipients_payload.append({"channel": "sms", "status": sms_result["status"]})
                recipients_payload.append({"channel": "whatsapp", "status": wa_result["status"]})
            if email:
                email_result = send_email(email, f"Oil Change Due - {machine_name}", message)
                recipients_payload.append({"channel": "email", "status": email_result["status"]})

        # Owner always gets a copy (per spec: "Employee Phone Number" + "Owner Email")
        if OWNER_EMAIL:
            send_email(OWNER_EMAIL, f"Oil Change Due - {machine_name}", message)
        if OWNER_PHONE:
            send_sms(OWNER_PHONE, message)

        # Log it to the in-app notification center
        try:
            api_post(
                "/notifications/ingest",
                {
                    "type": "Oil Change Reminder",
                    "title": f"Oil Change Due - {machine_name}",
                    "message": message,
                    "machine": machine.get("_id"),
                    "sourceCollection": "OilChange",
                    "sourceId": record.get("_id"),
                },
            )
        except requests.RequestException as exc:
            logger.error(f"Failed to log notification for {record.get('_id')}: {exc}")

        # Mark as sent so it doesn't fire again tomorrow
        try:
            api_patch(f"/oil-changes/{record['_id']}/mark-reminder-sent")
            logger.info(f"Reminder sent + marked for oil change {record['_id']} ({machine_name})")
        except requests.RequestException as exc:
            logger.error(f"Failed to mark reminder sent for {record.get('_id')}: {exc}")


def process_maintenance_due():
    logger.info("Checking maintenance due today...")
    due_records = api_get("/maintenance/due/today").get("data", [])
    logger.info(f"Found {len(due_records)} maintenance reminder(s) due")

    for record in due_records:
        machine = record.get("machine") or {}
        machine_name = machine.get("machineName", "Unknown machine")
        assigned_employees = machine.get("assignedEmployees", []) or []

        message = (
            f"Machine: {machine_name}\n"
            f"Scheduled maintenance is due today.\n"
            f"Please perform the required maintenance and log it in the system."
        )

        for emp in assigned_employees:
            if emp.get("phoneNumber"):
                send_sms(emp["phoneNumber"], message)
            if emp.get("email"):
                send_email(emp["email"], f"Maintenance Due - {machine_name}", message)

        if OWNER_EMAIL:
            send_email(OWNER_EMAIL, f"Maintenance Due - {machine_name}", message)

        try:
            api_post(
                "/notifications/ingest",
                {
                    "type": "Upcoming Maintenance",
                    "title": f"Maintenance Due - {machine_name}",
                    "message": message,
                    "machine": machine.get("_id"),
                    "sourceCollection": "Maintenance",
                    "sourceId": record.get("_id"),
                },
            )
        except requests.RequestException as exc:
            logger.error(f"Failed to log maintenance notification: {exc}")


def run_daily_checks():
    logger.info(f"=== Daily check started at {datetime.now().isoformat()} ===")
    try:
        process_oil_changes()
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Oil change check failed: {exc}")

    try:
        process_maintenance_due()
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Maintenance check failed: {exc}")

    logger.info("=== Daily check complete ===")


def main():
    parser = argparse.ArgumentParser(description="Machine Maintenance scheduler service")
    parser.add_argument("--now", action="store_true", help="Run the checks once immediately and exit")
    args = parser.parse_args()

    if not SCHEDULER_API_KEY:
        logger.warning("SCHEDULER_API_KEY is not set - backend calls will be rejected (401)")

    if args.now:
        run_daily_checks()
        sys.exit(0)

    hour = int(os.getenv("DAILY_CHECK_HOUR", "8"))
    minute = int(os.getenv("DAILY_CHECK_MINUTE", "0"))

    scheduler = BlockingScheduler()
    scheduler.add_job(run_daily_checks, "cron", hour=hour, minute=minute, id="daily_maintenance_check")
    logger.info(f"Scheduler started. Daily check will run at {hour:02d}:{minute:02d} every day.")
    logger.info("Press Ctrl+C to exit.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
    finally:
        scheduler.shutdown(wait=False)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
