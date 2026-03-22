# AI Fundraise Tracker

A fully automated AI startup funding tracker. Scrapes deals from Google News and TechCrunch every 12 hours, extracts structured data using Kimi K2, and publishes to a static website via GitHub Pages.

**Cost: ~$0.10-0.30/month** (just Kimi K2 API calls). Everything else is free.

---

## Architecture

```
Google News RSS (10 AI funding queries)
  + TechCrunch Venture RSS
            ↓
   Python ingestion script (GitHub Actions, every 12h)
            ↓
   Kimi K2 API extracts structured deal data
   (company, round, amount, investors, category)
            ↓
   Deduplicate against existing deals
            ↓
   Update docs/deals.json → commit to repo
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
│   └── ingest.py               # Main pipeline: collect → filter → extract → save
├── docs/
│   ├── index.html              # Frontend website (served by GitHub Pages)
│   └── deals.json              # Auto-generated deal data
├── requirements.txt
└── README.md
```

---

## Setup Guide (One-Time, ~10 minutes)

### Step 1: Get a Kimi (Moonshot AI) API Key

1. Go to [platform.moonshot.ai](https://platform.moonshot.ai/)
2. Sign up and create an API key
3. Recharge $1 to activate your account
4. Pricing: ~$0.60/M input tokens, ~$2.50/M output — your monthly cost will be $0.10-0.30

### Step 2: Set Up the GitHub Repository

1. Fork or push this project to a new GitHub repo
2. Go to **Settings → Pages**
   - Source: **Deploy from a branch**
   - Branch: `main`, folder: `/docs`
   - Save
3. Go to **Settings → Secrets and variables → Actions**
4. Add this **Repository Secret**:

| Secret Name | Value |
|---|---|
| `KIMI_API_KEY` | Your Moonshot/Kimi API key from Step 1 |

### Step 3: Test It

1. Go to **Actions** tab in your GitHub repo
2. Find the workflow "AI Fundraise Tracker — Ingest & Publish"
3. Click **Run workflow** → **Run workflow**
4. Watch the logs — you should see deals being collected and added
5. Visit `https://yourusername.github.io/ai-fundraise-tracker/` to see your site

---

## How It Works

### Ingestion (`scripts/ingest.py`)

1. **Collect**: Pulls articles from 10 Google News RSS queries + TechCrunch RSS
2. **Filter**: Keeps only articles that match AI keywords AND funding patterns
3. **Extract**: Sends each relevant article to Kimi K2 API, which returns structured JSON (company, round, amount, investors, etc.)
4. **Deduplicate**: Checks company name + date against existing deals (fuzzy 7-day window)
5. **Save**: Updates `docs/deals.json` directly — no external database needed

### Frontend (`docs/index.html`)

- Pure static HTML/CSS/JS — no framework, no build step
- Fetches `deals.json` on page load
- Search, filter by round, sort by any column
- Responsive, works on mobile
- Hosted free on GitHub Pages

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

**"Kimi API error"**
- Check your API key and that you have credits remaining at platform.moonshot.ai.

---

## Future Roadmap

- [ ] Twitter/X API integration for real-time VC monitoring
- [ ] Community "Submit a deal" form
- [ ] Weekly email digest of new deals
- [ ] Analytics page (trends by category, top investors, etc.)
- [ ] RSS feed output so others can subscribe
