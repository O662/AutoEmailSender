"""Application configuration loaded from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # SMTP
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Sender
    FROM_NAME = os.getenv("FROM_NAME", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "")

    # Tracking server
    TRACKING_HOST = os.getenv("TRACKING_HOST", "0.0.0.0")
    TRACKING_PORT = int(os.getenv("TRACKING_PORT", "5000"))
    TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "http://localhost:5000")

    # Email sending
    DELAY_BETWEEN_EMAILS = int(os.getenv("DELAY_BETWEEN_EMAILS", "10"))
    CONTACTS_CSV = os.getenv("CONTACTS_CSV", "contacts.csv")
    EMAIL_TEMPLATE = os.getenv("EMAIL_TEMPLATE", "templates/email_template.html")

    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "email_tracker.db")
