"""
AI Fundraise Tracker — Google Alerts Gmail Parser
Reads Google Alerts emails from a Gmail inbox and extracts article links.
These are fed into the same Claude extraction pipeline as RSS articles.

Setup:
1. Create Google Alerts for AI funding queries (delivered to your Gmail)
2. Enable Gmail API on the same Google Cloud project
3. Add Gmail scope to the service account OR use an App Password

This script uses IMAP with an App Password for simplicity.
"""

import os
import re
import email
import imaplib
import logging
from datetime import datetime, timedelta
from email.header import decode_header
from html.parser import HTMLParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "3"))


class LinkExtractor(HTMLParser):
    """Extract URLs from HTML content."""
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, val in attrs:
                if attr == "href" and val and "google.com/url" in val:
                    # Extract actual URL from Google redirect
                    match = re.search(r"url=([^&]+)", val)
                    if match:
                        from urllib.parse import unquote
                        self.links.append(unquote(match.group(1)))


def fetch_google_alerts():
    """Connect to Gmail via IMAP and extract Google Alerts articles."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        log.warning("Gmail credentials not set, skipping Google Alerts")
        return []

    articles = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        # Search for Google Alerts emails from the last N days
        since_date = (datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
        _, message_ids = mail.search(None, f'(FROM "googlealerts-noreply@google.com" SINCE {since_date})')

        if not message_ids[0]:
            log.info("No Google Alerts emails found")
            mail.logout()
            return []

        ids = message_ids[0].split()
        log.info(f"Found {len(ids)} Google Alerts emails")

        for msg_id in ids[:20]:  # Cap at 20 emails
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            subject = ""
            raw_subject = msg.get("Subject", "")
            decoded = decode_header(raw_subject)
            for part, enc in decoded:
                if isinstance(part, bytes):
                    subject += part.decode(enc or "utf-8", errors="replace")
                else:
                    subject += part

            # Get HTML body
            html_body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
            else:
                if msg.get_content_type() == "text/html":
                    html_body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            if html_body:
                extractor = LinkExtractor()
                extractor.feed(html_body)
                for link in extractor.links:
                    # Skip google internal links
                    if "google.com" in link or "support.google" in link:
                        continue
                    articles.append({
                        "title": subject,
                        "link": link,
                        "published": msg.get("Date", ""),
                        "summary": subject,
                        "source": "google_alerts",
                    })

        mail.logout()
        log.info(f"Extracted {len(articles)} article links from Google Alerts")

    except Exception as e:
        log.warning(f"Gmail IMAP error: {e}")

    return articles


if __name__ == "__main__":
    articles = fetch_google_alerts()
    for a in articles:
        print(f"  - {a['title'][:80]}")
        print(f"    {a['link']}")
