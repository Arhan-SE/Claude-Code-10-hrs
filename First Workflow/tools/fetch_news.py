"""
fetch_news.py — Tavily news fetcher for Align Lending newsletter.

Runs 5 targeted mortgage/housing searches, deduplicates results,
extracts rate hints, and writes .tmp/news_data.json.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

SEARCH_QUERIES = [
    "mortgage rates today 30 year fixed 2026",
    "Federal Reserve interest rate decision mortgage impact 2026",
    "housing market home prices affordability 2026",
    "mortgage refinancing trends applications 2026",
    "first time homebuyer programs FHA VA loans 2026",
    "commercial real estate mortgage lending 2026",
    "CFPB mortgage regulation lender compliance 2026",
]

OUTPUT_PATH = Path(__file__).parent.parent / ".tmp" / "news_data.json"
CACHE_HOURS = 6


def is_cache_fresh() -> bool:
    if not OUTPUT_PATH.exists():
        return False
    try:
        data = json.loads(OUTPUT_PATH.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        age = datetime.now(timezone.utc) - fetched_at
        return age < timedelta(hours=CACHE_HOURS)
    except Exception:
        return False


def run_searches(client: TavilyClient) -> list[dict]:
    all_results = []
    for query in SEARCH_QUERIES:
        try:
            print(f"  Searching: {query}")
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=7,
                include_raw_content=False,
            )
            results = response.get("results", [])
            all_results.extend(results)
            print(f"    → {len(results)} results")
        except Exception as e:
            print(f"  Warning: search failed for '{query}': {e}")
    return all_results


def deduplicate(results: list[dict]) -> list[dict]:
    seen_urls = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(r)
    # Sort by Tavily score descending, take top 15
    unique.sort(key=lambda x: x.get("score", 0), reverse=True)
    return unique[:15]


def extract_rate_hints(results: list[dict]) -> dict:
    """Scan titles and snippets for specific rate percentages."""
    rate_hints = {
        "30_year_fixed": None,
        "15_year_fixed": None,
        "fed_funds_rate": None,
    }

    # Patterns to match e.g. "6.85%", "7.1 percent"
    pct_pattern = re.compile(r"(\d+\.?\d*)\s*(?:%|percent)", re.IGNORECASE)

    texts_30yr = []
    texts_15yr = []
    texts_fed = []

    for r in results:
        combined = f"{r.get('title', '')} {r.get('content', '')[:300]}"
        if re.search(r"30.year|30yr", combined, re.IGNORECASE):
            texts_30yr.append(combined)
        if re.search(r"15.year|15yr", combined, re.IGNORECASE):
            texts_15yr.append(combined)
        if re.search(r"fed.funds|federal.funds|fed rate", combined, re.IGNORECASE):
            texts_fed.append(combined)

    def first_rate(texts):
        for text in texts:
            m = pct_pattern.search(text)
            if m:
                val = float(m.group(1))
                if 2.0 <= val <= 12.0:  # Reasonable mortgage rate range
                    return f"{val:.2f}%"
        return None

    rate_hints["30_year_fixed"] = first_rate(texts_30yr)
    rate_hints["15_year_fixed"] = first_rate(texts_15yr)
    rate_hints["fed_funds_rate"] = first_rate(texts_fed)

    return rate_hints


def save_results(articles: list[dict], rate_hints: dict) -> str:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "rate_hints": rate_hints,
        "articles": [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "content": a.get("content", ""),
                "score": a.get("score", 0),
                "published_date": a.get("published_date", ""),
            }
            for a in articles
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return str(OUTPUT_PATH)


def main(force: bool = False):
    if not force and is_cache_fresh():
        print(f"Cache is fresh (< {CACHE_HOURS}h old). Using existing {OUTPUT_PATH}")
        print("Run with --force to re-fetch.")
        return

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("ERROR: TAVILY_API_KEY not set in .env")
        sys.exit(1)

    print("[fetch_news] Starting Tavily searches...")
    client = TavilyClient(api_key=api_key)

    try:
        raw_results = run_searches(client)
    except Exception as e:
        print(f"ERROR: Tavily search failed: {e}")
        print("Check your API key and quota at https://app.tavily.com")
        sys.exit(1)

    if len(raw_results) < 3:
        print("ERROR: Fewer than 3 articles returned. Cannot generate newsletter.")
        sys.exit(1)

    articles = deduplicate(raw_results)
    rate_hints = extract_rate_hints(articles)

    path = save_results(articles, rate_hints)
    print(f"[fetch_news] Done. {len(articles)} articles saved to {path}")
    print(f"[fetch_news] Rate hints: {rate_hints}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch mortgage news via Tavily")
    parser.add_argument("--force", action="store_true", help="Bypass cache and re-fetch")
    args = parser.parse_args()
    main(force=args.force)
