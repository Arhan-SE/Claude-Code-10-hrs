"""
generate_infographics.py — OpenAI DALL-E 3 image generator for Align Lending newsletter.

Generates 2 infographic images via OpenAI's DALL-E 3 model:
  1. Rate Watch — a mortgage rate data dashboard visual (30yr, 15yr, Fed funds)
  2. Market Outlook — a housing market trend and affordability visual

Downloads the images and base64-encodes them as data URIs,
then saves them to .tmp/infographics.json for use by generate_newsletter.py.
"""

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OUTPUT_PATH = Path(__file__).parent.parent / ".tmp" / "infographics.json"


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in .env")
        sys.exit(1)

    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except ImportError:
        print("ERROR: openai not installed. Run: pip install openai")
        sys.exit(1)


def build_prompts(article_titles: list[str]) -> dict[str, str]:
    """Build targeted prompts for each infographic based on actual newsletter data."""

    topics = ", ".join(t[:60] for t in article_titles[:3]) if article_titles else "mortgage rates, housing market trends"

    rate_prompt = (
        "A sleek, premium financial infographic banner for a mortgage industry newsletter. "
        "Wide banner (16:9). Shows three data stat boxes side-by-side labeled: "
        "'30-YR FIXED', '15-YR FIXED', 'FED FUNDS RATE'. "
        "Design: dark navy (#1A2332) background with bold white percentage numbers, red (#E31E24) accent highlights, "
        "and steel blue-gray (#6B7B8D) secondary elements. "
        "Subtle background: upward trend line graph, faint grid lines, small house icon silhouette. "
        "Clean sans-serif typography, no photographs, purely data visualization and financial infographic design. "
        "Premium, editorial quality — like a Bloomberg or Freddie Mac mortgage market report visual."
    )

    market_prompt = (
        f"A sophisticated housing market trend infographic for a premium mortgage industry newsletter. "
        f"Wide banner (16:9). Visual elements: line chart showing mortgage rate trends over 12 months, "
        f"small house/home icon, subtle bar graphs for home price index or affordability index. "
        f"Color palette: dark navy background, red accent lines, white text, steel blue-gray secondary tones. "
        f"Topic context: {topics}. "
        f"No people, no photos — purely abstract data visualization, charts, and financial icons. "
        f"Premium editorial infographic aesthetic, like a high-end real estate research publication."
    )

    return {
        "rates": rate_prompt,
        "market": market_prompt,
    }


def generate_image(client, prompt: str, label: str) -> str | None:
    """Call OpenAI DALL-E 3, download the result, return base64 data URI."""
    print(f"  Generating {label} infographic via OpenAI DALL-E 3...")
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
    except Exception as e:
        print(f"  Warning: DALL-E 3 generation failed for {label}: {e}")
        return None

    image_url = response.data[0].url if response.data else None
    if not image_url:
        print(f"  Warning: No URL in OpenAI response for {label}")
        return None

    print(f"  Downloading {label} image from OpenAI...")
    try:
        with urllib.request.urlopen(image_url, timeout=60) as resp:
            raw_bytes = resp.read()
    except Exception as e:
        print(f"  Warning: Failed to download image for {label}: {e}")
        return None

    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"
    size_kb = len(raw_bytes) // 1024
    print(f"  {label} infographic ready ({size_kb}KB)")
    return data_uri


def main(article_titles: list[str] | None = None) -> dict[str, str | None]:
    """
    Generate infographics and save to .tmp/infographics.json.
    Returns dict: {"rates": data_uri_or_none, "market": data_uri_or_none}
    """
    client = get_openai_client()

    article_titles = article_titles or []

    prompts = build_prompts(article_titles)
    results = {}

    for key, prompt in prompts.items():
        data_uri = generate_image(client, prompt, key)
        results[key] = data_uri

    # Save to .tmp for inspection / reuse
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Store only a summary (not the full base64) in the saved file for readability
    summary = {k: (f"[base64 png, {len(v) // 1024}KB]" if v else None) for k, v in results.items()}
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2))
    print(f"[generate_infographics] Done. Summary saved to {OUTPUT_PATH}")

    return results


if __name__ == "__main__":
    # Standalone test: load article titles from existing news_data.json if available
    news_path = Path(__file__).parent.parent / ".tmp" / "news_data.json"
    titles = []
    if news_path.exists():
        data = json.loads(news_path.read_text())
        titles = [a.get("title", "") for a in data.get("articles", [])]

    results = main(article_titles=titles)
    for k, v in results.items():
        status = f"{len(v) // 1024}KB data URI" if v else "FAILED"
        print(f"  {k}: {status}")
