"""Flask tracking server — serves open-tracking pixel and click redirects."""

import base64
import re
import urllib.parse
from flask import Flask, request, redirect, Response, render_template_string
from config import Config
from database import init_db, record_event, get_tracking_summary, get_events_for_email

app = Flask(__name__)

# 1x1 transparent GIF (43 bytes)
TRACKING_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# ---------------------------------------------------------------------------
# Tracking endpoints
# ---------------------------------------------------------------------------

@app.route("/track/open/<email_id>.gif")
def track_open(email_id):
    """Record an email open event and return a 1x1 transparent GIF."""
    record_event(
        email_id=email_id,
        event_type="open",
        ip=request.remote_addr,
        ua=request.headers.get("User-Agent"),
    )
    return Response(TRACKING_PIXEL, mimetype="image/gif", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    })


@app.route("/track/click/<email_id>")
def track_click(email_id):
    """Record a link click event and redirect to the actual URL."""
    url = request.args.get("url", "")
    if not url:
        return "Missing url parameter", 400

    record_event(
        email_id=email_id,
        event_type="click",
        metadata=url,
        ip=request.remote_addr,
        ua=request.headers.get("User-Agent"),
    )
    return redirect(url)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Tracking Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f172a; color: #e2e8f0; padding: 2rem; }
        h1 { color: #f8fafc; margin-bottom: 0.5rem; font-size: 1.8rem; }
        .subtitle { color: #94a3b8; margin-bottom: 2rem; }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem; margin-bottom: 2rem;
        }
        .stat-card {
            background: #1e293b; border-radius: 12px; padding: 1.5rem;
            text-align: center; border: 1px solid #334155;
        }
        .stat-card .value { font-size: 2.5rem; font-weight: 700; color: #38bdf8; }
        .stat-card .label { color: #94a3b8; font-size: 0.85rem; margin-top: 0.25rem; }
        .stat-card.opens .value { color: #4ade80; }
        .stat-card.clicks .value { color: #a78bfa; }
        .stat-card.failed .value { color: #f87171; }

        table { width: 100%; border-collapse: collapse; background: #1e293b;
                border-radius: 12px; overflow: hidden; border: 1px solid #334155; }
        th { background: #334155; color: #f1f5f9; text-align: left;
             padding: 0.85rem 1rem; font-weight: 600; font-size: 0.85rem;
             text-transform: uppercase; letter-spacing: 0.05em; }
        td { padding: 0.75rem 1rem; border-top: 1px solid #334155;
             font-size: 0.9rem; }
        tr:hover td { background: #263348; }

        .badge {
            display: inline-block; padding: 0.2rem 0.6rem;
            border-radius: 9999px; font-size: 0.75rem; font-weight: 600;
        }
        .badge-sent { background: #164e63; color: #22d3ee; }
        .badge-failed { background: #7f1d1d; color: #fca5a5; }
        .badge-pending { background: #3b3b1f; color: #fde047; }
        .badge-yes { background: #14532d; color: #86efac; }
        .badge-no { background: #1e293b; color: #64748b; border: 1px solid #475569; }

        .detail-link { color: #38bdf8; text-decoration: none; }
        .detail-link:hover { text-decoration: underline; }

        .refresh { display: inline-block; margin-bottom: 1.5rem; color: #38bdf8;
                   text-decoration: none; font-size: 0.9rem; }
        .refresh:hover { text-decoration: underline; }

        .event-list { list-style: none; }
        .event-list li { padding: 0.5rem 0; border-bottom: 1px solid #334155;
                         font-size: 0.85rem; }
        .event-list li:last-child { border-bottom: none; }
        .event-type { font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }
        .event-type.open { color: #4ade80; }
        .event-type.click { color: #a78bfa; }
        .event-meta { color: #94a3b8; font-size: 0.8rem; word-break: break-all; }

        .back-link { color: #38bdf8; text-decoration: none; font-size: 0.9rem; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Email Tracking Dashboard</h1>
    <p class="subtitle">Real-time delivery, open, and click tracking</p>
    <a class="refresh" href="/">Refresh</a>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{{ summary.total_sent }}</div>
            <div class="label">Emails Sent</div>
        </div>
        <div class="stat-card failed">
            <div class="value">{{ summary.total_failed }}</div>
            <div class="label">Failed</div>
        </div>
        <div class="stat-card opens">
            <div class="value">{{ summary.total_opens }}</div>
            <div class="label">Unique Opens ({{ summary.open_rate }}%)</div>
        </div>
        <div class="stat-card clicks">
            <div class="value">{{ summary.total_clicks }}</div>
            <div class="label">Unique Clicks ({{ summary.click_rate }}%)</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Recipient</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Sent At</th>
                <th>Opened</th>
                <th>Clicked</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
        {% for e in summary.emails %}
            <tr>
                <td>{{ e.name }} &lt;{{ e.email }}&gt;</td>
                <td>{{ e.subject }}</td>
                <td>
                    {% if e.status == 'sent' %}
                        <span class="badge badge-sent">Sent</span>
                    {% elif e.status == 'failed' %}
                        <span class="badge badge-failed">Failed</span>
                    {% else %}
                        <span class="badge badge-pending">Pending</span>
                    {% endif %}
                </td>
                <td>{{ e.sent_at or '—' }}</td>
                <td>
                    {% if e.open_count > 0 %}
                        <span class="badge badge-yes">{{ e.open_count }}x</span>
                    {% else %}
                        <span class="badge badge-no">No</span>
                    {% endif %}
                </td>
                <td>
                    {% if e.click_count > 0 %}
                        <span class="badge badge-yes">{{ e.click_count }}x</span>
                    {% else %}
                        <span class="badge badge-no">No</span>
                    {% endif %}
                </td>
                <td><a class="detail-link" href="/detail/{{ e.id }}">View</a></td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Email Detail</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f172a; color: #e2e8f0; padding: 2rem; }
        h1 { color: #f8fafc; margin-bottom: 0.5rem; font-size: 1.5rem; }
        .back-link { color: #38bdf8; text-decoration: none; font-size: 0.9rem; }
        .back-link:hover { text-decoration: underline; }
        .info { margin: 1.5rem 0; }
        .info p { margin: 0.3rem 0; font-size: 0.95rem; }
        .info strong { color: #94a3b8; }
        .event-list { list-style: none; margin-top: 1rem; }
        .event-list li { padding: 0.6rem 0; border-bottom: 1px solid #334155;
                         font-size: 0.85rem; }
        .event-list li:last-child { border-bottom: none; }
        .event-type { font-weight: 600; text-transform: uppercase; font-size: 0.75rem;
                      padding: 0.15rem 0.5rem; border-radius: 9999px; }
        .event-type.open { color: #4ade80; background: #14532d; }
        .event-type.click { color: #a78bfa; background: #2e1065; }
        .event-meta { color: #94a3b8; font-size: 0.8rem; word-break: break-all; }
    </style>
</head>
<body>
    <a class="back-link" href="/">&larr; Back to Dashboard</a>
    <h1 style="margin-top:1rem;">Email Detail</h1>
    <div class="info">
        <p><strong>To:</strong> {{ email.recipient_name }} &lt;{{ email.recipient_email }}&gt;</p>
        <p><strong>Subject:</strong> {{ email.subject }}</p>
        <p><strong>Status:</strong> {{ email.status }}</p>
        <p><strong>Sent at:</strong> {{ email.sent_at or '—' }}</p>
    </div>
    <h2 style="font-size:1.1rem; margin-top:1.5rem;">Events ({{ events|length }})</h2>
    {% if events %}
    <ul class="event-list">
        {% for ev in events %}
        <li>
            <span class="event-type {{ ev.event_type }}">{{ ev.event_type }}</span>
            &mdash; {{ ev.created_at }}
            {% if ev.metadata %}
                <br><span class="event-meta">URL: {{ ev.metadata }}</span>
            {% endif %}
            <br><span class="event-meta">IP: {{ ev.ip_address or 'unknown' }}
            &bull; UA: {{ ev.user_agent or 'unknown' }}</span>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p style="margin-top:0.5rem; color:#64748b;">No tracking events yet.</p>
    {% endif %}
</body>
</html>
"""


@app.route("/")
def dashboard():
    """Render the tracking dashboard."""
    summary = get_tracking_summary()
    return render_template_string(DASHBOARD_TEMPLATE, summary=summary)


@app.route("/detail/<email_id>")
def email_detail(email_id):
    """Show detailed tracking events for a single email."""
    from database import get_connection
    conn = get_connection()
    row = conn.execute("""
        SELECT e.id, e.subject, e.status, e.sent_at, e.error_message,
               r.name AS recipient_name, r.email AS recipient_email
        FROM emails e
        JOIN recipients r ON e.recipient_id = r.id
        WHERE e.id = ?
    """, (email_id,)).fetchone()
    conn.close()

    if not row:
        return "Email not found", 404

    events = get_events_for_email(email_id)
    return render_template_string(DETAIL_TEMPLATE, email=dict(row), events=events)


# ---------------------------------------------------------------------------
# Helpers used by the email sender
# ---------------------------------------------------------------------------

def get_tracking_pixel_url(email_id: str) -> str:
    """Generate the tracking pixel image URL for an email."""
    base = Config.TRACKING_BASE_URL.rstrip("/")
    return f"{base}/track/open/{email_id}.gif"


def rewrite_links(html: str, email_id: str) -> str:
    """Replace all <a href="..."> links with tracked redirect URLs."""
    base = Config.TRACKING_BASE_URL.rstrip("/")

    def replace_href(match):
        original_url = match.group(1)
        # Don't rewrite mailto: or anchor links
        if original_url.startswith(("mailto:", "#", "tel:")):
            return match.group(0)
        encoded = urllib.parse.quote(original_url, safe="")
        tracked = f"{base}/track/click/{email_id}?url={encoded}"
        return match.group(0).replace(original_url, tracked)

    return re.sub(r'href=["\']([^"\']+)["\']', replace_href, html)


# ---------------------------------------------------------------------------
# Main entry point to run tracking server standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print(f"Tracking server running on http://{Config.TRACKING_HOST}:{Config.TRACKING_PORT}")
    print(f"Dashboard: {Config.TRACKING_BASE_URL}")
    app.run(
        host=Config.TRACKING_HOST,
        port=Config.TRACKING_PORT,
        debug=False,
    )
