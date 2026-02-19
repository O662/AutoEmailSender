"""Email sender — reads contacts, renders templates, sends via SMTP."""

import csv
import smtplib
import time
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Template

from config import Config
from database import (
    init_db,
    upsert_recipient,
    create_email_record,
    mark_email_sent,
    mark_email_failed,
)
from tracker import get_tracking_pixel_url, rewrite_links


def load_contacts(csv_path: str) -> list[dict]:
    """Load contacts from a CSV file. Expects columns: name, email."""
    contacts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            email = row.get("email", "").strip()
            if name and email:
                contacts.append({"name": name, "email": email})
    return contacts


def load_template(template_path: str) -> Template:
    """Load a Jinja2 HTML template from disk."""
    return Template(Path(template_path).read_text(encoding="utf-8"))


def build_email(
    recipient_name: str,
    recipient_email: str,
    subject: str,
    html_body: str,
    email_id: str,
) -> MIMEMultipart:
    """Construct a MIME email with tracking pixel injected."""
    # Rewrite links for click tracking
    html_body = rewrite_links(html_body, email_id)

    # Inject tracking pixel before </body>
    pixel_url = get_tracking_pixel_url(email_id)
    pixel_tag = f'<img src="{pixel_url}" width="1" height="1" alt="" style="display:none" />'
    if "</body>" in html_body:
        html_body = html_body.replace("</body>", f"{pixel_tag}</body>")
    else:
        html_body += pixel_tag

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{Config.FROM_NAME} <{Config.FROM_EMAIL}>"
    msg["To"] = f"{recipient_name} <{recipient_email}>"
    msg.attach(MIMEText(html_body, "html"))
    return msg


def send_emails(subject: str, template_path: str = None, csv_path: str = None):
    """Main send loop — loads contacts, renders, and sends one-by-one."""
    csv_path = csv_path or Config.CONTACTS_CSV
    template_path = template_path or Config.EMAIL_TEMPLATE

    init_db()

    # Load data
    contacts = load_contacts(csv_path)
    if not contacts:
        print("No contacts found. Check your CSV file.")
        return

    template = load_template(template_path)
    total = len(contacts)
    print(f"Loaded {total} contact(s) from {csv_path}")
    print(f"Delay between emails: {Config.DELAY_BETWEEN_EMAILS}s")
    print("-" * 60)

    # Connect to SMTP
    try:
        if Config.SMTP_USE_TLS:
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
            server.ehlo()

        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        print("SMTP connection established.\n")
    except Exception as e:
        print(f"Failed to connect to SMTP server: {e}")
        return

    # Send loop
    for i, contact in enumerate(contacts, 1):
        name = contact["name"]
        email = contact["email"]

        # Save to database
        rid = upsert_recipient(name, email)
        eid = create_email_record(rid, subject)

        # Render template with personalization variables
        html = template.render(
            name=name,
            first_name=name.split()[0] if name else "",
            email=email,
        )

        msg = build_email(name, email, subject, html, eid)

        try:
            server.sendmail(Config.FROM_EMAIL, email, msg.as_string())
            mark_email_sent(eid)
            print(f"[{i}/{total}] Sent to {name} <{email}>")
        except Exception as e:
            mark_email_failed(eid, str(e))
            print(f"[{i}/{total}] FAILED for {name} <{email}>: {e}")

        # Throttle — wait between emails (skip after the last one)
        if i < total:
            print(f"         Waiting {Config.DELAY_BETWEEN_EMAILS}s...")
            time.sleep(Config.DELAY_BETWEEN_EMAILS)

    server.quit()
    print("\n" + "=" * 60)
    print(f"Done! {total} email(s) processed.")
    print(f"View tracking dashboard: {Config.TRACKING_BASE_URL}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sender.py \"Your Email Subject\"")
        print("       python sender.py \"Subject\" --csv contacts.csv --template templates/email_template.html")
        sys.exit(1)

    subject = sys.argv[1]

    # Simple arg parsing
    csv_file = None
    tmpl_file = None
    args = sys.argv[2:]
    for idx, arg in enumerate(args):
        if arg == "--csv" and idx + 1 < len(args):
            csv_file = args[idx + 1]
        elif arg == "--template" and idx + 1 < len(args):
            tmpl_file = args[idx + 1]

    send_emails(subject, template_path=tmpl_file, csv_path=csv_file)
