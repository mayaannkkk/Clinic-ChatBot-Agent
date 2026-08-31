from langchain.tools import tool
import pandas as pd
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# The LLM has been observed inventing placeholder data ("John Doe",
# "johndoe@example.com") instead of asking the patient for their real
# details. Prompt instructions alone are not a reliable enough guard
# against this, so we also reject known-fake patterns here in code.
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


@tool
def book_appointment(name: str, email: str, date_time_str: str) -> str:
    """
    Books a fixed appointment and sends a confirmation email to the patient.

    Args:
        name: The patient's full name.
        email: The patient's email address.
        date_time_str: Date/time in format 'YYYY-MM-DD H:MM AM/PM'

    Returns:
        Confirmation message with email status, or an error message.
    """
    if _looks_like_placeholder(name, email):
        return (
            f"❌ Error: '{name}' / '{email}' looks like placeholder/example data, "
            "not a real patient's name and email. Ask the patient for their actual "
            "name and email address before booking."
        )

    try:
        dt = pd.to_datetime(date_time_str)
    except Exception:
        return f"❌ Error: '{date_time_str}' is not a valid date/time format."

    # Server-side safety net: the UI validates picker/typed input before this
    # tool is ever called, but the tool must never assume that happened —
    # the LLM could call this with anything. Never trust the caller alone.
    if not (8 <= dt.hour < 12 or 16 <= dt.hour < 22):
        return f"❌ Error: {date_time_str} is outside clinic hours (8:00 AM-12:00 PM and 4:00 PM-10:00 PM)."

    if dt < pd.Timestamp.now():
        return f"❌ Error: {date_time_str} is in the past. Please choose a future date and time."

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

    return f"✅ Appointment booked for {name} on {date_str} at {time_str}. {email_status}"