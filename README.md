# AI Fundraise Tracker

A fully automated AI startup funding tracker. Scrapes deals from Google News, TechCrunch, and Google Alerts every 12 hours, extracts structured data using Claude, stores it in Google Sheets, and publishes to a static website via GitHub Pages.

**Cost: ~$0.10-0.30/month** (just Kimi K2 API calls). Everything else is free.

---

## Architecture

```
Google News RSS (8 AI funding queries)
  + Google Alerts → Gmail inbox → parsed by script
  + TechCrunch Venture RSS
            ↓
   Python ingestion script (GitHub Actions, every 12h)
            ↓
   Kimi K2 API extracts structured deal data
   (company, round, amount, investors, category)
            ↓
   Deduplicate against existing rows
            ↓
   Append new deals to Google Sheet
            ↓
   Export to deals.json → commit to repo
            ↓
   GitHub Pages serves your website
```

---

## Project Structure

```
ai-fundraise-tracker/
├── .github/workflows/
│   └── ingest.yml              # GitHub Actions cron (every 12h)
├── scripts/
│   ├── ingest.py               # Main pipeline: collect → filter → extract → append
│   ├── export_json.py          # Export sheet → deals.json
│   └── google_alerts.py        # Gmail parser for Google Alerts
├── docs/
│   ├── index.html              # Frontend website (served by GitHub Pages)
│   └── deals.json              # Auto-generated deal data (DO NOT EDIT)
├── requirements.txt
└── README.md
```

---

## Setup Guide (One-Time, ~30 minutes)

### Step 1: Create a Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "ai-fundraise-tracker")
3. Enable these APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Go to **IAM & Admin → Service Accounts**
5. Click **Create Service Account**
   - Name: `ai-fundraise-bot`
   - Click **Create and Continue**
   - Skip the optional role/access steps
   - Click **Done**
6. Click on the service account → **Keys** → **Add Key** → **Create new key** → **JSON**
7. Download the JSON file — this is your `GOOGLE_CREDENTIALS_JSON`

### Step 2: Create the Google Sheet

1. Create a new Google Sheet
2. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_SHEET_ID/edit`
3. **Share the sheet** with the service account email
   (looks like `ai-fundraise-bot@your-project.iam.gserviceaccount.com`)
   - Give it **Editor** access
4. The script will auto-create headers on first run. Or manually add them:
   `Company | Description | Category | Round | Amount_M | Valuation_M | Investors | Date | Source_URL | Added_At`

### Step 3: Get a Kimi (Moonshot AI) API Key

1. Go to [platform.moonshot.ai](https://platform.moonshot.ai/)
2. Sign up and create an API key
3. Recharge $1 to activate your account (when you reach $5 cumulative, you get a $5 bonus — so $1 gets you started for months)
4. Pricing: ~$0.60/M input tokens, ~$2.50/M output — your monthly cost will be $0.10-0.30

### Step 4: Set Up Google Alerts (Optional but Recommended)

1. Go to [google.com/alerts](https://www.google.com/alerts)
2. Create alerts for these queries:
   - `AI startup funding round`
   - `artificial intelligence series A`
   - `generative AI raised`
   - `machine learning startup venture capital`
   - `LLM company funding`
3. Set delivery to: **Email** (your Gmail)
4. Frequency: **As it happens** or **Once a day**

### Step 5: Create Gmail App Password (only if using Google Alerts)

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. You need 2FA enabled on your Google account
3. Create an App Password for "Mail"
4. Save the 16-character password

### Step 6: Set Up the GitHub Repository

1. Fork or push this project to a new GitHub repo
2. Go to **Settings → Pages**
   - Source: **Deploy from a branch**
   - Branch: `main`, folder: `/docs`
   - Save
3. Go to **Settings → Secrets and variables → Actions**
4. Add these **Repository Secrets**:

| Secret Name | Value |
|---|---|
| `GOOGLE_SHEET_ID` | Your Sheet ID from Step 2 |
| `GOOGLE_CREDENTIALS_JSON` | Entire contents of the JSON key file from Step 1 |
| `KIMI_API_KEY` | Your Moonshot/Kimi API key from Step 3 |
| `GMAIL_USER` | Your Gmail address (optional, for Google Alerts) |
| `GMAIL_APP_PASSWORD` | App Password from Step 5 (optional) |

### Step 7: Test It

1. Go to **Actions** tab in your GitHub repo
2. Find the workflow "AI Fundraise Tracker — Ingest & Publish"
3. Click **Run workflow** → **Run workflow**
4. Watch the logs — you should see deals being collected and added
5. After it completes, check your Google Sheet for new rows
6. Visit `https://yourusername.github.io/ai-fundraise-tracker/` to see your site

---

## How It Works

### Ingestion (`scripts/ingest.py`)

1. **Collect**: Pulls articles from 8 Google News RSS queries + TechCrunch RSS
2. **Filter**: Keeps only articles that match AI keywords AND funding patterns
3. **Extract**: Sends each relevant article to Claude API, which returns structured JSON (company, round, amount, investors, etc.)
4. **Deduplicate**: Checks company name + date against existing sheet rows (fuzzy 7-day window)
5. **Append**: Adds new deals to the Google Sheet

### Export (`scripts/export_json.py`)

1. Reads all rows from the "Deals" sheet
2. Cleans and validates data types
3. Sorts by date (newest first)
4. Writes `docs/deals.json`

### Frontend (`docs/index.html`)

- Pure static HTML/CSS/JS — no framework, no build step
- Fetches `deals.json` on page load
- Search, filter by round, sort by any column
- Responsive, works on mobile
- Hosted free on GitHub Pages

---

## Manual Deal Entry

For deals the automation misses (especially from LinkedIn/Twitter):

1. Open your Google Sheet
2. Go to the "Deals" tab
3. Add a row with the deal info
4. The next export cycle (or manual workflow trigger) will pick it up

**Tip**: Create a second tab called "Manual Input" as a staging area where you dump raw links, then clean them into the Deals tab periodically.

---

## Customization

### Change scraping frequency
Edit `.github/workflows/ingest.yml`:
```yaml
# Every 6 hours instead of 12
- cron: "0 0,6,12,18 * * *"
```

### Add more search queries
Edit `GOOGLE_NEWS_QUERIES` in `scripts/ingest.py`.

### Add more categories
Edit `CATEGORY_MAP` in `scripts/ingest.py`.

### Custom domain
Add a `docs/CNAME` file with your domain (e.g., `aifundraise.dev`).

---

## Troubleshooting

**"No new deals found"**
- Normal if run frequently. The RSS feeds may not have new AI funding articles.
- Try broadening `GOOGLE_NEWS_QUERIES` or increasing `LOOKBACK_DAYS`.

**"Google Sheet permission denied"**
- Make sure you shared the sheet with the service account email as Editor.

**"Claude API error"**
- Check your API key and that you have credits remaining.

**"Gmail IMAP error"**
- Make sure 2FA is enabled and the App Password is correct.
- Google Alerts is optional — the pipeline works fine without it.

---

## Future Roadmap

- [ ] Twitter/X API integration ($100/mo) for real-time VC monitoring
- [ ] Community "Submit a deal" form
- [ ] Weekly email digest of new deals
- [ ] Analytics page (trends by category, top investors, etc.)
- [ ] RSS feed output so others can subscribe
