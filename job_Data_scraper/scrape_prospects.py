"""
Scrapes LinkedIn founder/CTO/eng-leader profiles (with email) via the
HarvestAPI Apify actor, filters out haram-adjacent companies, and writes
a CSV of prospects.

Usage:
    python3 scrape_prospects.py
"""

import csv
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
ACTOR_ID = "harvestapi~linkedin-profile-search"
APIFY_BASE = "https://api.apify.com/v2"

# --- search configuration ---
SEARCH_QUERY = (
    '"Technical Recruiter" OR "Talent Acquisition" OR "HR Manager" '
    'OR "HR Business Partner" OR "Recruiter"'
)
LOCATIONS = [
    "United Arab Emirates",
    "Saudi Arabia",
    "Qatar",
    "Kuwait",
    "Bahrain",
    "Oman",
]
SENIORITY_LEVEL_IDS = [
    "320",  # Owner / Partner
    "310",  # CXO
    "220",  # Director
    "210",  # Experienced Manager
    "200",  # Entry Level Manager
    "130",  # Strategic
    "120",  # Senior
]
INDUSTRY_IDS = [
    "4",
    "3102",
]  # Software Development, IT System Custom Software Development

# Free-tier accounts are capped at 25 profiles per actor run regardless of
# maxItems, so to reach real volume we run multiple batches, each requesting
# a different LinkedIn search results page (startPage) so batches don't just
# return the same top 25 profiles over and over.
ITEMS_PER_BATCH = 25
TARGET_TOTAL_PROSPECTS = int(os.environ.get("TARGET_TOTAL_PROSPECTS", 450))
NUM_BATCHES = -(-TARGET_TOTAL_PROSPECTS // ITEMS_PER_BATCH)  # ceil division
BATCH_DELAY_SECONDS = 5  # pause between batches, free-tier friendly

# keywords used to drop haram-adjacent companies (best-effort, not exhaustive —
# always eyeball the output CSV before using it)
EXCLUDE_KEYWORDS = [
    "casino",
    "betting",
    "gambling",
    "bookmaker",
    "sportsbook",
    "brewery",
    "beer",
    "wine",
    "vodka",
    "whisky",
    "whiskey",
    "liquor",
    "alcohol",
    "bank",
    "lending",
    "loan",
    "mortgage",
    "interest-based",
    "conventional finance",
    "adult content",
    "adult entertainment",
    "dating app",
    "escort",
    "pork",
    "bacon",
    "ham producer",
]

# company-name keywords that indicate an agency/consultancy/IT-services shop
# rather than a software product company (best-effort text match on name only)
SERVICES_COMPANY_KEYWORDS = [
    "consulting",
    "consultancy",
    "consultants",
    "agency",
    "studio",
    "it services",
    "managed services",
    "outsourcing",
    "staffing",
    "solutions ltd",
    "solutions llc",
    "solutions inc",
]

RATE_LIMIT_SECONDS = 2  # delay between polling requests, free-tier friendly
MAX_POLL_ATTEMPTS = 60
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__),
    "output",
    os.environ.get("OUTPUT_FILENAME", "gcc_prospects.csv"),
)


def run_actor(start_page):
    if not APIFY_TOKEN:
        sys.exit(
            "APIFY_TOKEN not set. Copy .env.example to .env and fill in your token."
        )

    payload = {
        "profileScraperMode": "Full + email search",
        "searchQuery": SEARCH_QUERY,
        "locations": LOCATIONS,
        "seniorityLevelIds": SENIORITY_LEVEL_IDS,
        "industryIds": INDUSTRY_IDS,
        "maxItems": ITEMS_PER_BATCH,
        "startPage": start_page,
    }

    print(f"Starting actor run (page {start_page}, max {ITEMS_PER_BATCH} profiles)...")
    resp = requests.post(
        f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
        params={"token": APIFY_TOKEN},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    run = resp.json()["data"]
    run_id = run["id"]
    print(f"Run started: {run_id}")
    return run_id


def wait_for_run(run_id):
    for attempt in range(MAX_POLL_ATTEMPTS):
        time.sleep(RATE_LIMIT_SECONDS)
        resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": APIFY_TOKEN},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["status"]
        print(f"  poll {attempt + 1}: status={status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            return data
    sys.exit("Timed out waiting for actor run to finish.")


def fetch_dataset(dataset_id):
    resp = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": APIFY_TOKEN, "format": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def current_company_name(item):
    positions = item.get("currentPosition") or []
    return positions[0].get("companyName", "") if positions else ""


def best_email(item):
    emails = item.get("emails") or []
    valid = [e for e in emails if e.get("status") == "valid"]
    if valid:
        return valid[0].get("email", "")
    if emails:
        return emails[0].get("email", "")
    return ""


def location_text(item):
    location = item.get("location") or {}
    parsed = location.get("parsed") or {}
    return parsed.get("text") or location.get("linkedinText", "")


def is_excluded(item):
    company = current_company_name(item).lower()
    haystack = " ".join(
        [
            company,
            item.get("headline", "") or "",
            item.get("about", "") or "",
        ]
    ).lower()
    if any(keyword in haystack for keyword in EXCLUDE_KEYWORDS):
        return True
    if any(keyword in company for keyword in SERVICES_COMPANY_KEYWORDS):
        return True
    return False


def to_row(item):
    return {
        "first_name": item.get("firstName", ""),
        "last_name": item.get("lastName", ""),
        "linkedin_url": item.get("linkedinUrl", ""),
        "title": item.get("headline", ""),
        "company": current_company_name(item),
        "email": best_email(item),
        "location": location_text(item),
    }


def run_one_batch(start_page):
    run_id = run_actor(start_page)
    run_data = wait_for_run(run_id)
    if run_data["status"] != "SUCCEEDED":
        print(f"  batch (page {start_page}) did not succeed: {run_data['status']}, skipping")
        return []
    return fetch_dataset(run_data["defaultDatasetId"])


def main():
    seen_urls = set()
    rows = []
    excluded_count = 0

    for batch_num in range(1, NUM_BATCHES + 1):
        if len(rows) >= TARGET_TOTAL_PROSPECTS:
            break

        items = run_one_batch(start_page=batch_num)
        print(f"Batch {batch_num}/{NUM_BATCHES}: fetched {len(items)} raw profiles.")

        for item in items:
            url = item.get("linkedinUrl", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            if is_excluded(item):
                excluded_count += 1
                continue
            rows.append(to_row(item))

        if not items:
            print("Batch returned no profiles — result pool exhausted, stopping.")
            break

        if batch_num < NUM_BATCHES:
            time.sleep(BATCH_DELAY_SECONDS)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "first_name",
                "last_name",
                "linkedin_url",
                "title",
                "company",
                "email",
                "location",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Excluded {excluded_count} profiles via keyword filter.")
    print(f"Wrote {len(rows)} unique prospects to {OUTPUT_PATH}")
    print(
        "Review the CSV manually — keyword filtering is best-effort, not a guarantee."
    )


if __name__ == "__main__":
    main()
