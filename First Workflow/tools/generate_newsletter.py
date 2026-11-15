"""
generate_newsletter.py — OpenAI GPT-4o HTML email generator for Align Lending.

Reads .tmp/news_data.json, generates infographics via fal.ai (nano-banana),
builds a fully branded HTML email, and writes .tmp/newsletter.html.
"""

import base64
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Import infographic generator (same tools/ directory)
sys.path.insert(0, str(Path(__file__).parent))
import generate_infographics

INPUT_PATH = Path(__file__).parent.parent / ".tmp" / "news_data.json"
OUTPUT_PATH = Path(__file__).parent.parent / ".tmp" / "newsletter.html"
LOGO_PATH = Path(__file__).parent.parent / "brand-assets" / "logo.png"


def load_news() -> dict:
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found. Run fetch_news.py first.")
        sys.exit(1)
    data = json.loads(INPUT_PATH.read_text())
    if len(data.get("articles", [])) < 3:
        print("ERROR: Fewer than 3 articles in news_data.json. Re-run fetch_news.py.")
        sys.exit(1)
    return data


def encode_logo() -> str | None:
    if not LOGO_PATH.exists():
        print(f"Warning: Logo not found at {LOGO_PATH}. Will use text fallback.")
        return None
    raw = LOGO_PATH.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def inject_infographics(html: str, infographics: dict) -> str:
    """Replace placeholder comments in the HTML with actual <img> tags from the image generator."""
    img_style = (
        'style="display:block; width:100%; max-width:560px; height:auto; '
        'border-radius:10px; margin:16px 0; border:1px solid #E8E8E8;" '
        'alt="Align Lending AI Infographic"'
    )
    placeholder_html = (
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">'
        '<tr><td style="background:linear-gradient(135deg,#1A2332 0%,#2d3f52 100%); '
        'border-radius:10px; padding:28px 20px; text-align:center; '
        'border:1px solid rgba(107,123,141,0.4);">'
        '<div style="color:#E31E24; font-size:10px; font-weight:bold; letter-spacing:3px; '
        'text-transform:uppercase; margin-bottom:6px;">AI-GENERATED INFOGRAPHIC</div>'
        '<div style="color:rgba(255,255,255,0.4); font-size:9px; letter-spacing:1px;">'
        'POWERED BY OPENAI · GENERATING VISUAL INTELLIGENCE</div>'
        '</td></tr></table>'
    )

    for key, data_uri in infographics.items():
        placeholder = f"<!-- FAL_INFOGRAPHIC_{key.upper()} -->"
        if placeholder not in html:
            continue
        if data_uri:
            img_tag = f'<img src="{data_uri}" {img_style}>'
            html = html.replace(placeholder, img_tag)
            print(f"  Injected {key} infographic into HTML")
        else:
            html = html.replace(placeholder, placeholder_html)
            print(f"  Used placeholder for {key} infographic (generation failed)")

    return html


def inject_logo(html: str, logo_uri: str | None) -> str:
    """Replace <!-- LOGO_PLACEHOLDER --> with the actual base64 logo img tag."""
    if logo_uri:
        img_tag = (
            f'<img src="{logo_uri}" height="72" '
            f'style="display:block; border:0; max-width:220px; height:auto; max-height:72px;" '
            f'alt="Align Lending">'
        )
        print("  Injected logo into HTML")
    else:
        img_tag = (
            '<div style="font-family:Arial,Helvetica,sans-serif; font-size:26px; font-weight:bold; '
            'letter-spacing:2px; color:#1A2332;">ALIGN<span style="color:#E31E24;">LENDING</span></div>'
        )
        print("  Logo not found — using text fallback")
    return html.replace("<!-- LOGO_PLACEHOLDER -->", img_tag)


def build_prompts(news_data: dict) -> tuple[str, str]:
    date_str = datetime.now().strftime("%B %d, %Y")
    articles = news_data.get("articles", [])

    # Pass substantial content so GPT can write full paragraphs
    articles_trimmed = []
    for a in articles[:10]:
        articles_trimmed.append({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "content": a.get("content", "")[:1200],
            "published_date": a.get("published_date", ""),
        })

    week_num = datetime.now().isocalendar()[1]
    year = datetime.now().year

    rate_hints = news_data.get("rate_hints", {})
    rate_30yr = rate_hints.get("30_year_fixed") or "N/A"
    rate_15yr = rate_hints.get("15_year_fixed") or "N/A"
    rate_fed = rate_hints.get("fed_funds_rate") or "N/A"

    system_prompt = """You are an expert HTML email developer and senior mortgage industry analyst for Align Lending.

CRITICAL OUTPUT RULES:
- Output ONLY raw HTML. Start with <!DOCTYPE html> and end with </html>.
- Do NOT output markdown, code fences, explanations, or any text outside the HTML.
- ALL CSS must be inline style="" attributes — NO <style> blocks.
- Use table-based layout. Wrap the entire email in a centered outer table, max-width 600px.

CONTENT RULES:
- Every story must have a FULL PARAGRAPH of analysis — minimum 4 sentences per story, not bullet points.
- Every story headline must be a clickable hyperlink to the actual source URL provided.
- Write like a senior mortgage analyst: authoritative, specific, data-driven, practical.
- Include actual numbers, rates, and percentages whenever present in the source material.
- Paragraphs should explain context, significance, and what it means for borrowers or lenders.

BRAND SPEC:
- Primary red: #E31E24
- Steel blue-gray: #6B7B8D
- Dark navy: #1A2332
- Off-white section bg: #F7F8FA
- Body text: #2C2C2C
- Secondary text: #666666
- Font: Arial, Helvetica, sans-serif

PLACEHOLDERS (do NOT write img tags — they are injected automatically):
- Logo: <!-- LOGO_PLACEHOLDER --> (placed in the white header area)
- Infographic 1: <!-- FAL_INFOGRAPHIC_RATES --> (placed in Rate Watch section)
- Infographic 2: <!-- FAL_INFOGRAPHIC_MARKET --> (placed in Market Outlook section)
"""

    articles_json = json.dumps(articles_trimmed, indent=2, ensure_ascii=False)

    user_prompt = f"""Generate the Align Lending Weekly Mortgage Market Briefing for {date_str}. Edition #{week_num}, {year}.

RATE DATA FROM SEARCH (use these values in the Rate Watch stat boxes if available):
- 30-Year Fixed: {rate_30yr}
- 15-Year Fixed: {rate_15yr}
- Fed Funds Rate: {rate_fed}

NEWS ARTICLES (select 4–5 of the most significant and newsworthy mortgage/housing stories):
{articles_json}

Build this EXACT premium email layout — follow every detail precisely:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1: MASTHEAD HEADER (3 layers)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Layer 1A — Red accent stripe:
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td style="background:#E31E24; height:5px; font-size:0; line-height:0;">&nbsp;</td></tr>
</table>

Layer 1B — White logo zone (padding: 24px 40px, background: #FFFFFF, text-align: center):
  - <!-- LOGO_PLACEHOLDER --> (this comment exactly — logo img injected automatically)
  - Below logo: a pill badge: <span style="display:inline-block; margin-top:10px; padding:4px 14px; background:#F7F8FA; border:1px solid #E8E8E8; border-radius:20px; font-size:10px; letter-spacing:2px; color:#6B7B8D; text-transform:uppercase; font-weight:bold;">Mortgage Intelligence</span>

Layer 1C — Dark navy brand bar (background: #1A2332, padding: 14px 40px, text-align: center):
  - "WEEKLY MORTGAGE MARKET BRIEFING" in white, font-size:11px, letter-spacing:4px, font-weight:bold, text-transform:uppercase
  - <div style="color:#6B7B8D; font-size:10px; letter-spacing:1px; margin-top:4px;">{date_str} &nbsp;·&nbsp; Edition #{week_num}</div>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2: IN THIS ISSUE (teaser strip)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background: #F7F8FA, padding: 16px 40px, border-bottom: 2px solid #E8E8E8
- Label: "IN THIS ISSUE" in #E31E24, font-size:9px, font-weight:bold, letter-spacing:3px, text-transform:uppercase
- Bulleted list of 4–5 story topics in #2C2C2C, font-size:12px, line-height:1.8, margin-top:6px
  Format each as: <span style="color:#E31E24; font-weight:bold;">·</span> [short story topic]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3: RATE WATCH (data dashboard)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background: #FFFFFF, padding: 32px 40px

Section label row (use a table, 2 columns):
  Left: <div style="display:inline-block; border-bottom:2px solid #E31E24; padding-bottom:4px; font-size:10px; font-weight:bold; letter-spacing:3px; color:#E31E24; text-transform:uppercase;">📊 RATE WATCH</div>
  Right: <span style="font-size:10px; color:#999999;">Week {week_num} Snapshot</span>

IMPORTANT: Place this comment on its own line right after the section label row: <!-- FAL_INFOGRAPHIC_RATES -->

Three stat boxes using a <table width="100%"> with 3 <td> cells (width="33%"), cellpadding="6" cellspacing="8":
Each stat box: background:#1A2332, border-radius:10px, padding:18px 12px, text-align:center
  - Category label: font-size:9px, font-weight:bold, text-transform:uppercase, letter-spacing:2px, color:#6B7B8D, margin-bottom:8px
  - Main value: font-size:26px, font-weight:bold, color:#FFFFFF, display:block, line-height:1
  - Trend: ▲ in #FF7A7A (rate rising = bad for borrowers) or ▼ in #7AE87A (rate falling = good), font-size:12px, margin:6px 0 2px
  - Sub-note: font-size:9px, color:rgba(255,255,255,0.45)

Box 1 — Label: "30-YR FIXED" | Value: {rate_30yr} (use "~7%" if N/A, sourced from news) | Trend: based on direction from news | Note: "national avg"
Box 2 — Label: "15-YR FIXED" | Value: {rate_15yr} (use "~6.3%" if N/A, sourced from news) | Trend: based on direction | Note: "national avg"
Box 3 — Label: "FED FUNDS" | Value: {rate_fed} (use "4.25–4.5%" if N/A) | Trend: based on Fed posture | Note: "target range"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4: THIS WEEK IN MORTGAGE (story cards)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background: #F7F8FA, padding: 28px 40px

Section header:
  <div style="border-left:4px solid #E31E24; padding-left:14px; margin-bottom:24px;">
    <div style="font-size:18px; font-weight:bold; color:#1A2332; letter-spacing:-0.5px; line-height:1.2;">This Week in Mortgage</div>
    <div style="font-size:11px; color:#6B7B8D; margin-top:3px;">What's moving markets and what it means for you</div>
  </div>

4–5 story cards, each as a <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px; border-radius:10px; border:1px solid #E8E8E8; background:#FFFFFF;">
Each card <td style="padding:22px 24px; border-radius:10px;">:

  Row A — Number pill + category tag:
    <span style="background:#E31E24; color:white; font-size:9px; font-weight:bold; padding:2px 8px; border-radius:10px; margin-right:8px;">01</span> (02, 03, 04, 05)
    <span style="font-size:9px; font-weight:bold; text-transform:uppercase; letter-spacing:1px; color:#6B7B8D;">[CATEGORY]</span>
    Categories: RATES, HOUSING MARKET, FEDERAL RESERVE, REGULATION, REFINANCING, FIRST-TIME BUYERS, INDUSTRY NEWS

  Row B — Headline (clickable link to ACTUAL source URL from article data):
    <a href="[EXACT_URL_FROM_ARTICLE_DATA]" style="font-size:16px; font-weight:bold; color:#1A2332; text-decoration:none; line-height:1.4; display:block; margin:10px 0 0;">[HEADLINE]</a>

  Row C — Full analysis paragraph (MINIMUM 4 sentences, no bullets):
    <p style="font-size:13px; color:#444444; line-height:1.85; margin:12px 0 14px;">
      [Write a full analytical paragraph. Include: what happened, specific numbers/rates/percentages from the article, why it matters to borrowers or lenders, and what the likely next development will be. Minimum 4 sentences.]
    </p>

  Row D — Source attribution with link:
    <div style="font-size:10px; color:#999999; border-top:1px solid #F0F0F0; padding-top:10px;">
      Source: <a href="[EXACT_URL_FROM_ARTICLE_DATA]" style="color:#6B7B8D; text-decoration:underline;">[PUBLICATION NAME]</a> &nbsp;·&nbsp; [DATE] &nbsp;·&nbsp; <span style="color:#E31E24; font-weight:bold;">Read full article →</span>
    </div>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5: MARKET OUTLOOK (expert analysis + CTA)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background: #FFFFFF, padding: 28px 40px

IMPORTANT: Place this comment on its own line at the very START of this section's <td>: <!-- FAL_INFOGRAPHIC_MARKET -->

Inner callout box: background:#F7F8FA, border-left:5px solid #E31E24, border-radius:0 10px 10px 0, padding:24px 28px

Inside the callout box:
- Label: <div style="font-size:9px; font-weight:bold; letter-spacing:3px; color:#E31E24; text-transform:uppercase; margin-bottom:12px;">💡 MARKET OUTLOOK</div>
- Opening quote mark: <div style="font-size:48px; line-height:1; color:#E31E24; margin-bottom:-12px; font-family:Georgia,serif;">"</div>
- Full analysis: Write 2 full paragraphs (4–5 sentences each). First paragraph: synthesize the week's biggest mortgage trends and rate movements. Second paragraph: what borrowers and lenders should watch for in the coming weeks, with specific actionable guidance.
  Style: font-size:14px, color:#2C2C2C, line-height:1.85, margin-bottom:12px
- Closing quote mark: <div style="font-size:48px; line-height:0.5; color:#E31E24; text-align:right; font-family:Georgia,serif;">"</div>
- CTA button (centered, margin-top:20px):
  <a href="https://alignlending.com" style="display:inline-block; background:#E31E24; color:#FFFFFF; padding:13px 32px; border-radius:4px; font-size:12px; font-weight:bold; letter-spacing:1px; text-decoration:none; text-transform:uppercase;">Talk to a Loan Officer →</a>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6: QUICK TAKE (pull quote)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background: #1A2332, padding: 28px 40px, text-align: center

- Label: <div style="font-size:9px; font-weight:bold; letter-spacing:3px; color:#E31E24; text-transform:uppercase; margin-bottom:16px;">🔑 THIS WEEK'S KEY TAKEAWAY</div>
- One authoritative sentence summarizing the single most important thing for mortgage borrowers or lenders to know this week.
  Style: font-size:17px, color:#FFFFFF, line-height:1.6, font-style:italic, max-width:460px, margin:0 auto

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7: FOOTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Background: #6B7B8D, padding: 28px 40px, text-align: center

- "ALIGN LENDING" in white, font-size:11px, font-weight:bold, letter-spacing:3px
- Tagline: "Your Trusted Mortgage Intelligence Partner." in rgba(255,255,255,0.6), font-size:10px, margin:6px 0 16px
- Divider: <div style="border-top:1px solid rgba(255,255,255,0.15); margin:16px 0;"></div>
- Contact: "info@alignlending.com &nbsp;·&nbsp; alignlending.com" in #D0D8E0, font-size:11px
- Legal (margin-top:14px): "This newsletter is for informational purposes only and does not constitute financial or investment advice. Rates shown are indicative and subject to change. Contact a licensed loan officer for personalized guidance." in rgba(255,255,255,0.45), font-size:9px, line-height:1.6
- Unsubscribe (margin-top:10px): <a href="#" style="color:rgba(255,255,255,0.35); font-size:9px; text-decoration:underline;">Unsubscribe</a>

WRITING STANDARDS:
- Every story section must be a real paragraph, not bullet points or sentence fragments.
- Use actual numbers, rates, and statistics from the source articles wherever possible.
- Every headline and source attribution must link to the actual article URL from the data provided.
- Write with authority — like a senior analyst at a top mortgage firm briefing their team.
"""

    return system_prompt, user_prompt


def call_openai(system: str, user: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in .env")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    print("[generate_newsletter] Calling GPT-4o...")

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=12000,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    html = response.choices[0].message.content or ""
    # Strip any accidental markdown code fences
    html = re.sub(r"```html?\s*", "", html)
    html = re.sub(r"```\s*$", "", html, flags=re.MULTILINE)
    return html.strip()


def validate_html(html: str) -> bool:
    checks = {
        "closing tag": "</html>" in html.lower(),
        "brand red color": "#E31E24" in html or "#e31e24" in html,
        "rate or number content": bool(re.search(r"\d+\.?\d*%|\$\d+", html)),
        "align lending": "align lending" in html.lower(),
    }
    all_pass = all(checks.values())
    failed = [k for k, v in checks.items() if not v]
    if failed:
        print(f"  Warning: HTML validation failed checks: {failed}")
    return all_pass


def main():
    print("[generate_newsletter] Loading news data...")
    news_data = load_news()
    print(f"  {len(news_data['articles'])} articles loaded")

    # ── Generate infographics via fal.ai nano-banana ──────────────────────────
    print("[generate_newsletter] Generating infographics via fal.ai (nano-banana)...")
    article_titles = [a.get("title", "") for a in news_data.get("articles", [])]
    infographics = generate_infographics.main(article_titles=article_titles)
    generated_count = sum(1 for v in infographics.values() if v)
    print(f"  {generated_count}/{len(infographics)} infographics generated")

    # ── Encode logo ───────────────────────────────────────────────────────────
    print("[generate_newsletter] Encoding logo...")
    logo_uri = encode_logo()
    if logo_uri:
        print(f"  Logo encoded ({len(logo_uri) // 1024}KB base64)")

    # ── Generate HTML via GPT-4o ──────────────────────────────────────────────
    system_prompt, user_prompt = build_prompts(news_data)
    html = call_openai(system_prompt, user_prompt)

    # ── Inject logo + fal.ai infographics into placeholder slots ─────────────
    print("[generate_newsletter] Injecting logo and infographics into HTML...")
    html = inject_logo(html, logo_uri)
    html = inject_infographics(html, infographics)

    # ── Validate and save ─────────────────────────────────────────────────────
    print("[generate_newsletter] Validating output...")
    valid = validate_html(html)
    if not valid:
        print("  Warning: Some validation checks failed but proceeding.")

    if "</html>" not in html.lower():
        print("ERROR: Generated HTML appears truncated (no </html> found).")
        print("Saving partial output for inspection...")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"[generate_newsletter] Done. Newsletter saved to {OUTPUT_PATH}")
    print(f"  Open in browser to preview: open '{OUTPUT_PATH}'")


if __name__ == "__main__":
    main()
