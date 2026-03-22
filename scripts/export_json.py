"""
AI Fundraise Tracker — Export Script
Reads the Google Sheet and exports deals.json for the static frontend.
Runs right after ingest.py in the same GitHub Actions workflow.
"""

import os
import json
import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "docs/deals.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON env var not set")
    creds_data = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def export_deals():
    log.info("Connecting to Google Sheet...")
    sheet = get_sheet()
    ws = sheet.worksheet("Deals")
    rows = ws.get_all_records()
    log.info(f"Read {len(rows)} deals from sheet")

    deals = []
    for row in rows:
        company = str(row.get("Company", "")).strip()
        if not company:
            continue

        # Parse amount
        amount = row.get("Amount_M", "")
        try:
            amount = float(amount) if amount else None
        except (ValueError, TypeError):
            amount = None

        # Parse valuation
        valuation = row.get("Valuation_M", "")
        try:
            valuation = float(valuation) if valuation else None
        except (ValueError, TypeError):
            valuation = None

        # Parse investors
        investors_raw = str(row.get("Investors", ""))
        investors = [i.strip() for i in investors_raw.split(",") if i.strip()]

        # Parse date
        date_str = str(row.get("Date", ""))
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            date_str = ""

        deals.append({
            "company": company,
            "desc": str(row.get("Description", "")),
            "category": str(row.get("Category", "")),
            "round": str(row.get("Round", "")),
            "amount": amount,
            "valuation": valuation,
            "investors": investors,
            "date": date_str,
            "source_url": str(row.get("Source_URL", "")),
        })

    # Sort by date descending
    deals.sort(key=lambda d: d.get("date", ""), reverse=True)

    # Write JSON
    output = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_deals": len(deals),
        "deals": deals,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Exported {len(deals)} deals to {OUTPUT_PATH}")
    log.info(f"Last updated: {output['last_updated']}")


if __name__ == "__main__":
    export_deals()
