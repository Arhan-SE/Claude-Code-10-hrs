"""
synthesize_content.py

Uses GPT-4.1 to read raw research results and produce a fully structured
newsletter JSON. This is the intelligence hub — everything downstream depends
on its output.

Usage:
    python tools/synthesize_content.py --topic "AI in healthcare"
    python tools/synthesize_content.py --topic "AI in healthcare" --audience "healthcare professionals" --tone "authoritative" --sections 5
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

RESEARCH_FILE = Path(".tmp/research_raw.json")
OUTPUT_FILE = Path(".tmp/content_structured.json")

SYSTEM_PROMPT = """You are an expert newsletter writer and content strategist.
Your job is to read raw research results and produce a polished, structured newsletter.
You always respond with valid JSON only — no markdown fences, no extra text."""

USER_PROMPT_TEMPLATE = """You are writing a newsletter about: "{topic}"

Target audience: {audience}
Tone: {tone}
Number of content sections: {sections}

Here is the raw research gathered on this topic:
<research>
{research_text}
</research>

Produce a JSON object with EXACTLY this structure:
{{
  "subject_line": "Compelling email subject line (max 60 chars)",
  "preview_text": "Preview/preheader text that appears after subject in inbox (max 90 chars)",
  "headline": "Main newsletter headline",
  "intro_paragraph": "Engaging opening paragraph (2-3 sentences) that hooks the reader",
  "sections": [
    {{
      "heading": "Section heading",
      "body": "2-4 paragraph section body. Well-written, factual, engaging. Use the research.",
      "key_stat": "One compelling statistic or quote from the research (or empty string if none)",
      "infographic": {{
        "type": "dalle3 OR matplotlib OR none",
        "prompt_or_data": "For dalle3: a detailed image generation prompt. For matplotlib: a JSON string like {{\\\"chart_type\\\": \\\"bar\\\", \\\"title\\\": \\\"...\\\", \\\"labels\\\": [...], \\\"values\\\": [...], \\\"y_label\\\": \\\"...\\\"}}. For none: empty string.",
        "caption": "Short image caption (or empty string if type is none)"
      }}
    }}
  ],
  "conclusion": "Closing paragraph tying everything together (2-3 sentences)",
  "cta_text": "Call-to-action button text (e.g. 'Read the full report')",
  "cta_url": "URL for the CTA (use the most relevant source URL from research, or '#')",
  "sources": ["list of source URLs cited in the newsletter"],
  "social_snippet": "A ready-to-post social media snippet about this newsletter (max 280 chars, no hashtags unless natural)"
}}

Rules:
- Use dalle3 for conceptual/illustrative images (hero visuals, topic illustrations)
- Use matplotlib ONLY when the research contains actual numerical data worth charting
- Use none if a section doesn't need a visual
- Include exactly {sections} items in the sections array
- Write in the specified tone throughout
- Ground all claims in the provided research
- Respond with JSON only"""


def run(topic: str, audience: str = "general professional", tone: str = "informative and engaging", sections: int = 4) -> dict:
    if not RESEARCH_FILE.exists():
        raise FileNotFoundError(f"{RESEARCH_FILE} not found. Run research_topic.py first.")

    research = json.loads(RESEARCH_FILE.read_text())
    research_text = "\n\n".join(
        f"[{i+1}] {r['title']}\nURL: {r['url']}\n{r['content']}"
        for i, r in enumerate(research)
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print(f"Synthesizing newsletter content with GPT-4.1 ({sections} sections)...")
    response = client.chat.completions.create(
        model="gpt-4.1",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                topic=topic,
                audience=audience,
                tone=tone,
                sections=sections,
                research_text=research_text,
            )},
        ],
        temperature=0.7,
    )

    content = json.loads(response.choices[0].message.content)

    # Basic validation
    required_keys = ["subject_line", "preview_text", "headline", "intro_paragraph",
                     "sections", "conclusion", "cta_text", "cta_url", "sources", "social_snippet"]
    for key in required_keys:
        if key not in content:
            raise ValueError(f"GPT-4.1 response missing required key: '{key}'")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(content, indent=2, ensure_ascii=False))

    print(f"Structured content saved → {OUTPUT_FILE}")
    print(f"  Subject: {content['subject_line']}")
    print(f"  Sections: {len(content['sections'])}")
    print(f"  Social snippet ready: {bool(content.get('social_snippet'))}")
    return content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthesize newsletter content with GPT-4.1.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--audience", default="general professional")
    parser.add_argument("--tone", default="informative and engaging")
    parser.add_argument("--sections", type=int, default=4)
    args = parser.parse_args()

    run(args.topic, args.audience, args.tone, args.sections)
