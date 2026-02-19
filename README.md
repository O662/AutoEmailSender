# AutoEmailSender

A personalized email sending tool with built-in **delivery**, **open**, and **click** tracking — all self-hosted with no third-party email services required.

---

## Features

- **CSV-based contact list** — add names and emails in a simple spreadsheet format
- **Jinja2 HTML templates** — personalize emails with `{{ name }}`, `{{ first_name }}`, `{{ email }}`
- **One-at-a-time sending** with configurable delays to avoid spam filters
- **Open tracking** — invisible 1x1 pixel records when recipients open the email
- **Click tracking** — all links are rewritten to pass through a redirect that logs clicks
- **Web dashboard** — real-time stats on sends, opens, and clicks with per-email detail views
- **SQLite storage** — zero-config database, no external services needed
- **SMTP support** — works with Gmail, Outlook, SendGrid, or any SMTP server

---

## Project Structure

```
AutoEmailSender/
├── config.py              # Configuration (loaded from .env)
├── database.py            # SQLite database layer
├── tracker.py             # Flask tracking server + dashboard
├── sender.py              # Email sender (SMTP)
├── contacts.csv           # Your contact list
├── templates/
│   └── email_template.html  # Email HTML template
├── requirements.txt
├── .env.example           # Example environment variables
└── .gitignore
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy the example and fill in your SMTP credentials:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_NAME=Your Name
FROM_EMAIL=your_email@gmail.com
TRACKING_BASE_URL=http://localhost:5000
DELAY_BETWEEN_EMAILS=10
```

> **Gmail users:** You need an [App Password](https://support.google.com/accounts/answer/185833), not your normal password. Enable 2FA first, then generate an app password.

### 3. Add your contacts

Edit `contacts.csv`:

```csv
name,email
Alice Johnson,alice@example.com
Bob Smith,bob@example.com
```

### 4. Customize your email template

Edit `templates/email_template.html`. Available template variables:

| Variable         | Description              |
|------------------|--------------------------|
| `{{ name }}`     | Full name from CSV       |
| `{{ first_name }}`| First word of the name  |
| `{{ email }}`    | Email address            |

### 5. Start the tracking server

In one terminal:

```bash
python tracker.py
```

This starts the Flask server that handles:
- Open tracking pixel requests
- Click redirect tracking
- The web dashboard at `http://localhost:5000`

### 6. Send emails

In another terminal:

```bash
python sender.py "Your Email Subject"
```

Optional flags:

```bash
python sender.py "Subject" --csv contacts.csv --template templates/email_template.html
```

### 7. View the dashboard

Open `http://localhost:5000` in your browser to see:

- Total emails sent / failed
- Open rate and click rate
- Per-recipient open and click counts
- Detailed event log per email (timestamps, IP, user agent)

---

## How Tracking Works

### Open Tracking

A tiny invisible image (1x1 pixel) is automatically injected into each email:

```html
<img src="http://yourserver.com/track/open/{email_id}.gif" width="1" height="1" />
```

When the recipient's email client loads images, it requests this URL, and the server records an "open" event.

> **Note:** Open tracking depends on the email client loading images. Some clients block images by default, so open rates may be underreported.

### Click Tracking

All `<a href="...">` links in your template are automatically rewritten:

```
Original:  https://example.com/page
Tracked:   http://yourserver.com/track/click/{email_id}?url=https%3A%2F%2Fexample.com%2Fpage
```

When clicked, the server logs the click event and immediately redirects to the original URL.

---

## Production Deployment

For tracking to work when recipients open emails from anywhere, the tracking server must be publicly accessible.

### Options:

1. **VPS/Cloud server** — deploy on DigitalOcean, AWS, etc. and point a domain to it
2. **ngrok** (for testing) — `ngrok http 5000` gives you a public URL
3. **Reverse proxy** — put behind Nginx/Caddy with HTTPS

Update `TRACKING_BASE_URL` in your `.env` to the public URL:

```env
TRACKING_BASE_URL=https://track.yourdomain.com
```

---

## Configuration Reference

All settings go in `.env`:

| Variable                | Default              | Description                                      |
|-------------------------|----------------------|--------------------------------------------------|
| `SMTP_HOST`             | `smtp.gmail.com`     | SMTP server hostname                             |
| `SMTP_PORT`             | `587`                | SMTP server port                                 |
| `SMTP_USERNAME`         |                      | SMTP login username                              |
| `SMTP_PASSWORD`         |                      | SMTP login password / app password               |
| `SMTP_USE_TLS`          | `true`               | Use STARTTLS                                     |
| `FROM_NAME`             |                      | Sender display name                              |
| `FROM_EMAIL`            |                      | Sender email address                             |
| `TRACKING_HOST`         | `0.0.0.0`            | Tracking server bind host                        |
| `TRACKING_PORT`         | `5000`               | Tracking server port                             |
| `TRACKING_BASE_URL`     | `http://localhost:5000` | Public URL for tracking links                 |
| `DELAY_BETWEEN_EMAILS`  | `10`                 | Seconds to wait between sends                    |
| `CONTACTS_CSV`          | `contacts.csv`       | Path to contacts CSV file                        |
| `EMAIL_TEMPLATE`        | `templates/email_template.html` | Path to email HTML template         |
| `DATABASE_PATH`         | `email_tracker.db`   | SQLite database file path                        |

---

## Limitations & Notes

- **Open tracking** relies on image loading — privacy-focused clients (Apple Mail Privacy Protection, some Outlook settings) may pre-fetch or block tracking pixels
- **Click tracking** is reliable since it requires an actual HTTP redirect
- Sending speed depends on your SMTP provider's rate limits — adjust `DELAY_BETWEEN_EMAILS` accordingly
- For high-volume sending, consider using a transactional email API (SendGrid, Mailgun) instead of raw SMTP

---

## TLDR:
- In termanal 1: python tracker.py
- In termanal 2: python sender.py "Hey, Just following up about the new website!"