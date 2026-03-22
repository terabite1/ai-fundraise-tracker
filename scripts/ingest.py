"""
AI Fundraise Tracker — Deal Ingestion Script
Pulls from Google News RSS, TechCrunch RSS.
Extracts structured deal data using Kimi K2 API (OpenAI-compatible).
Deduplicates and appends to docs/deals.json.
Runs every 12h via GitHub Actions.

API cost: ~$0.10-0.30/month with Kimi K2
"""

import os
import re
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from html import unescape

import feedparser
import requests

# ─── CONFIG ───────────────────────────────────────────────────
DEALS_PATH = os.environ.get("DEALS_PATH", "docs/deals.json")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "3"))

# Kimi K2 API (OpenAI-compatible)
KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_BASE_URL = "https://api.moonshot.ai/v1"
KIMI_MODEL = "kimi-k2-0905-preview"  # or "kimi-k2.5" for latest

# Google News RSS search queries
GOOGLE_NEWS_QUERIES = [
    "AI startup funding round",
    "artificial intelligence series raised",
    "generative AI seed funding",
    "AI company raises million",
    "machine learning startup venture capital",
    "LLM startup funding",
    "AI infrastructure funding round",
    "foundation model startup raised",
    "AI startup seed round 2025",
    "AI company series A 2026",
]

TECHCRUNCH_RSS = "https://techcrunch.com/category/venture/feed/"

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model", "generative ai", "gpt", "foundation model",
    "neural network", "computer vision", "nlp", "natural language",
    "robotics", "autonomous", "ml ops", "mlops", "ai agent",
    "ai infrastructure", "ai safety", "transformer", "diffusion model",
    "copilot", "chatbot", "multimodal", "text-to-", "speech-to-",
]

CATEGORY_MAP = {
    "Foundation Models": ["foundation model", "llm", "large language", "gpt", "transformer", "open-source model", "open-weight", "frontier model"],
    "AI Agents": ["ai agent", "autonomous agent", "agentic", "copilot", "ai assistant", "browser agent"],
    "Developer Tools": ["developer tool", "devtool", "sdk", "api platform", "code generation", "coding assistant", "ide"],
    "Enterprise AI": ["enterprise", "saas", "b2b", "workflow automation", "productivity", "search platform"],
    "Creative AI": ["image generation", "video generation", "music generation", "creative ai", "design ai", "text-to-image", "text-to-video"],
    "AI Infra": ["infrastructure", "compute", "gpu cloud", "training platform", "inference", "ai chip", "ai hardware"],
    "Data Infra": ["data platform", "data pipeline", "labeling", "annotation", "vector database", "data preprocessing"],
    "MLOps": ["mlops", "ml ops", "experiment tracking", "model monitoring", "model deployment", "feature store"],
    "Vertical AI": ["healthcare ai", "legal ai", "fintech ai", "biotech", "drug discovery", "climate ai", "education ai", "real estate ai"],
    "Robotics": ["robotics", "robot", "humanoid", "manipulation", "autonomous vehicle", "drone"],
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ─── JSON FILE STORAGE ────────────────────────────────────────

def load_existing_deals():
    """Load existing deals from the JSON file."""
    if not os.path.exists(DEALS_PATH):
        return []
    try:
        with open(DEALS_PATH, "r") as f:
            data = json.load(f)
        return data.get("deals", [])
    except (json.JSONDecodeError, IOError):
        return []


def save_deals(deals):
    """Write all deals back to the JSON file."""
    deals.sort(key=lambda d: d.get("date", ""), reverse=True)
    output = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_deals": len(deals),
        "deals": deals,
    }
    os.makedirs(os.path.dirname(DEALS_PATH) or ".", exist_ok=True)
    with open(DEALS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    log.info(f"Saved {len(deals)} deals to {DEALS_PATH}")


def deal_exists(existing_deals, company, date_str):
    company_lower = company.lower().strip()
    for deal in existing_deals:
        existing_company = str(deal.get("company", "")).lower().strip()
        existing_date = str(deal.get("date", ""))
        if company_lower in existing_company or existing_company in company_lower:
            try:
                d1 = datetime.strptime(date_str, "%Y-%m-%d")
                d2 = datetime.strptime(existing_date, "%Y-%m-%d")
                if abs((d1 - d2).days) <= 7:
                    return True
            except ValueError:
                if existing_company == company_lower:
                    return True
    return False


# ─── RSS SOURCES ──────────────────────────────────────────────

def fetch_google_news_rss(query, lookback_days=LOOKBACK_DAYS):
    encoded_query = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}+when:{lookback_days}d&hl=en-US&gl=US&ceid=US:en"
    articles = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            articles.append({
                "title": unescape(entry.get("title", "")),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": unescape(entry.get("summary", "")),
                "source": "google_news",
            })
    except Exception as e:
        log.warning(f"Google News RSS error for '{query}': {e}")
    return articles


def fetch_techcrunch_rss():
    articles = []
    try:
        feed = feedparser.parse(TECHCRUNCH_RSS)
        cutoff = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
        for entry in feed.entries[:20]:
            published = entry.get("published_parsed")
            if published:
                pub_dt = datetime(*published[:6])
                if pub_dt < cutoff:
                    continue
            articles.append({
                "title": unescape(entry.get("title", "")),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": unescape(entry.get("summary", ""))[:500],
                "source": "techcrunch",
            })
    except Exception as e:
        log.warning(f"TechCrunch RSS error: {e}")
    return articles


def is_ai_related(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in AI_KEYWORDS)


def is_funding_related(text):
    funding_patterns = [
        r"raise[ds]?\s+\$?\d+",
        r"funding\s+round",
        r"series\s+[a-e]",
        r"seed\s+(round|funding|raise)",
        r"pre-seed",
        r"venture\s+capital",
        r"\$\d+[\.\d]*\s*(million|billion|m|b)\s*(funding|round|raise|in)",
        r"led\s+by",
        r"valuation\s+of\s+\$",
        r"secures?\s+\$?\d+",
        r"closes?\s+\$?\d+",
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in funding_patterns)


# ─── KIMI K2 API FOR EXTRACTION (OpenAI-compatible) ──────────

def extract_deal_with_kimi(article):
    """Use Kimi K2 API to extract structured deal data from an article.

    Kimi uses the OpenAI-compatible /v1/chat/completions endpoint.
    Cost: ~$0.60/M input + $2.50/M output tokens = pennies per extraction.
    """
    if not KIMI_API_KEY:
        log.warning("No KIMI_API_KEY set, skipping Kimi extraction")
        return None

    prompt = f"""Extract the AI startup funding deal from this article. Return ONLY a JSON object, no markdown, no backticks, no explanation.

Article title: {article['title']}
Article summary: {article.get('summary', 'N/A')[:800]}
Published: {article.get('published', 'N/A')}

Return this exact JSON structure (use null for unknown fields):
{{
  "company": "Company Name",
  "desc": "One-line description of what the company does",
  "category": "One of: Foundation Models, AI Agents, Developer Tools, Enterprise AI, Creative AI, AI Infra, Data Infra, MLOps, Vertical AI, Robotics",
  "round": "e.g. Pre-Seed, Seed, Series A, Series B, Series C, Series D, Series E",
  "amount": 100,
  "valuation": 500,
  "investors": ["Lead Investor 1", "Investor 2"],
  "date": "YYYY-MM-DD",
  "is_valid_deal": true
}}

Rules:
- "amount" is in millions USD (number only, no $ sign). 100 means $100M.
- "valuation" is post-money valuation in millions USD. Use null if not mentioned.
- "is_valid_deal" should be false if this isn't actually a funding round announcement.
- "date" should be the deal announcement date in YYYY-MM-DD format. Use today's date if unclear.
- Only include this deal if the company is clearly AI/ML related."""

    try:
        resp = requests.post(
            f"{KIMI_BASE_URL}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {KIMI_API_KEY}",
            },
            json={
                "model": KIMI_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a structured data extraction assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()

        # Clean potential markdown fences
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        deal = json.loads(text)

        if not deal.get("is_valid_deal", False):
            return None
        deal.pop("is_valid_deal", None)
        deal["source_url"] = article.get("link", "")
        return deal

    except Exception as e:
        log.warning(f"Kimi extraction failed: {e}")
        return None


# ─── MAIN PIPELINE ────────────────────────────────────────────

def collect_articles():
    all_articles = []
    seen_titles = set()

    for query in GOOGLE_NEWS_QUERIES:
        log.info(f"Fetching Google News: '{query}'")
        articles = fetch_google_news_rss(query)
        for a in articles:
            title_hash = hashlib.md5(a["title"].lower().encode()).hexdigest()
            if title_hash not in seen_titles:
                seen_titles.add(title_hash)
                all_articles.append(a)
        time.sleep(1)

    log.info("Fetching TechCrunch Venture RSS")
    tc_articles = fetch_techcrunch_rss()
    for a in tc_articles:
        title_hash = hashlib.md5(a["title"].lower().encode()).hexdigest()
        if title_hash not in seen_titles:
            seen_titles.add(title_hash)
            all_articles.append(a)

    log.info(f"Collected {len(all_articles)} unique articles")
    return all_articles


def filter_relevant(articles):
    relevant = []
    for a in articles:
        text = f"{a['title']} {a.get('summary', '')}"
        if is_ai_related(text) and is_funding_related(text):
            relevant.append(a)
    log.info(f"Filtered to {len(relevant)} AI funding articles")
    return relevant


def run_pipeline():
    log.info("=" * 60)
    log.info("AI Fundraise Tracker — Ingestion Pipeline (Kimi K2)")
    log.info("=" * 60)

    # 1. Load existing deals from JSON
    existing_deals = load_existing_deals()
    log.info(f"Found {len(existing_deals)} existing deals")

    # 2. Collect articles from all sources
    articles = collect_articles()

    # 3. Filter for AI + funding relevance
    relevant = filter_relevant(articles)

    # 4. Extract structured deals using Kimi K2
    new_deals = []
    for i, article in enumerate(relevant):
        log.info(f"Extracting deal {i+1}/{len(relevant)}: {article['title'][:80]}...")
        deal = extract_deal_with_kimi(article)
        if deal and deal.get("company"):
            # 5. Deduplicate
            date_str = deal.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
            if not deal_exists(existing_deals, deal["company"], date_str):
                new_deals.append(deal)
                existing_deals.append(deal)  # prevent dupes within same run
                log.info(f"  ✓ New deal: {deal['company']} — {deal.get('round', '?')} — ${deal.get('amount', '?')}M")
            else:
                log.info(f"  ✗ Duplicate: {deal['company']}")
        time.sleep(1)  # Rate limit

    # 6. Save to JSON file
    if new_deals:
        all_deals = load_existing_deals() + new_deals
        save_deals(all_deals)
        log.info(f"Pipeline complete: {len(new_deals)} new deals added")
    else:
        log.info("Pipeline complete: no new deals found")

    return new_deals


if __name__ == "__main__":
    run_pipeline()
