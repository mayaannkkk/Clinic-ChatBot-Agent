from langchain.tools import tool
import pandas as pd
import os
import smtplib
import ssl
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


_PLACEHOLDER_NAMES = {
    "john doe", "jane doe", "test user", "test", "your name",
    "first last", "example user", "name", "n/a",
}
_PLACEHOLDER_EMAIL_SUBSTRINGS = (
    "example.com", "example.org", "example.net", "test@test",
    "your.email", "user@example", "email@example", "name@example",
    "placeholder", "yourname@", "domain.com",
)


def _looks_like_placeholder(name: str, email: str) -> bool:
    name_l = name.strip().lower()
    email_l = email.strip().lower()
    if name_l in _PLACEHOLDER_NAMES:
        return True
    if any(sub in email_l for sub in _PLACEHOLDER_EMAIL_SUBSTRINGS):
        return True
    return False


def _save_to_airtable(name: str, email: str, date_str: str, time_str: str) -> str:
    """
    Writes a booking record to Airtable. Never raises — always returns a
    status string, so a failure here can never break the actual booking.
    """
    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    table_name = os.environ.get("AIRTABLE_TABLE_NAME")

    if not (api_key and base_id and table_name):
        return "Airtable not configured (missing AIRTABLE_API_KEY/BASE_ID/TABLE_NAME) — skipped."

    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "fields": {
            "Name": name,
            "Email": email,
            "Date": date_str,
            "Time": time_str,
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code in (200, 201):
            return "Saved to Airtable."
        return f"Airtable error ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Airtable request failed: {e}"


@tool
def book_appointment(name: str, email: str, date_time_str: str) -> str:
    """
    Books a fixed appointment, sends a confirmation email, and logs the
    booking to Airtable.

    Args:
        name: The patient's full name.
        email: The patient's email address.
        date_time_str: Date/time in format 'YYYY-MM-DD H:MM AM/PM'

    Returns:
        Confirmation message with email and Airtable status, or an error message.
    """
    if _looks_like_placeholder(name, email):
        return (
            f" Error: '{name}' / '{email}' looks like placeholder/example data, "
            "not a real patient's name and email. Ask the patient for their actual "
            "name and email address before booking."
        )

    try:
        dt = pd.to_datetime(date_time_str)
    except Exception:
        return f" Error: '{date_time_str}' is not a valid date/time format."

    # Server-side safety net: the UI validates picker/typed input before this
    # tool is ever called, but the tool must never assume that happened —
    # the LLM could call this with anything. Never trust the caller alone.
    if not (8 <= dt.hour < 12 or 16 <= dt.hour < 22):
        return f" Error: {date_time_str} is outside clinic hours (8:00 AM-12:00 PM and 4:00 PM-10:00 PM)."

    if dt < pd.Timestamp.now():
        return f" Error: {date_time_str} is in the past. Please choose a future date and time."

    date_str = dt.strftime('%Y-%m-%d')
    time_str = dt.strftime('%I:%M %p').lstrip('0')

    # Try to send real email
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    email_status = "Mock email (real email not configured)"

    if sender and password:
        try:
            subject = f"Appointment Confirmation for {name}"
            body = f"""Dear {name},

Your appointment on {date_str} at {time_str} is confirmed.

Thank you for choosing our clinic.
"""
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            context = ssl.create_default_context()
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            email_status = f"Confirmation email sent to {email}"
        except Exception as e:
            email_status = f"Email failed: {str(e)}"

    # Log to Airtable — happens automatically, regardless of what the LLM does next.
    airtable_status = _save_to_airtable(name, email, date_str, time_str)

    return (
        f" Appointment booked for {name} on {date_str} at {time_str}. "
        f"{email_status}. {airtable_status}"
    )