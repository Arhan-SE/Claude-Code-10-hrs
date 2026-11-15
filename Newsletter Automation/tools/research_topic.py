"""
research_topic.py

Queries Tavily for a given topic and saves raw results to .tmp/research_raw.json.
This is the entry point of every newsletter generation run.

Usage:
    python tools/research_topic.py --topic "the rise of ambient computing in 2025"
    python tools/research_topic.py --topic "AI in healthcare" --max_results 15 --include_news
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

OUTPUT_FILE = Path(".tmp/research_raw.json")


def run(topic: str, max_results: int = 10, include_news: bool = False) -> list[dict]:
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    print(f"Searching Tavily for: '{topic}' (depth=advanced, max_results={max_results})")
    general_results = client.search(
        query=topic,
        search_depth="advanced",
        max_results=max_results,
    )["results"]

    news_results = []
    if include_news:
        print("Also fetching recent news...")
        news_results = client.search(
            query=topic,
            topic="news",
            days=30,
            max_results=5,
        )["results"]

    # Merge and deduplicate by URL
    seen_urls = set()
    merged = []
    for result in general_results + news_results:
        url = result.get("url", "")
        if url not in seen_urls:
            seen_urls.add(url)
            merged.append({
                "url": url,
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "score": result.get("score", 0),
            })

    # Drop very low-relevance results
    merged = [r for r in merged if r["score"] >= 0.3]
    merged.sort(key=lambda r: r["score"], reverse=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False))

    print(f"Saved {len(merged)} results → {OUTPUT_FILE}")
    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Research a topic using Tavily.")
    parser.add_argument("--topic", required=True, help="Topic to research")
    parser.add_argument("--max_results", type=int, default=10)
    parser.add_argument("--include_news", action="store_true", help="Also fetch recent news results")
    args = parser.parse_args()

    run(args.topic, args.max_results, args.include_news)
