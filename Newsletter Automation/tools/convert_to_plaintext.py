"""
convert_to_plaintext.py

Generates a clean plain text version of the newsletter from the compiled HTML.
Prepends subject line and preview text, appends sources.

Usage:
    python tools/convert_to_plaintext.py
"""

import argparse
import json
import re
from pathlib import Path

import html2text

HTML_FILE = Path(".tmp/newsletter.html")
CONTENT_FILE = Path(".tmp/content_structured.json")
OUTPUT_FILE = Path(".tmp/newsletter_plain.txt")


def run(
    html_file: Path = HTML_FILE,
    content_file: Path = CONTENT_FILE,
    output_file: Path = OUTPUT_FILE,
) -> None:
    if not html_file.exists():
        raise FileNotFoundError(f"{html_file} not found. Run build_newsletter_html.py first.")
    if not content_file.exists():
        raise FileNotFoundError(f"{content_file} not found. Run synthesize_content.py first.")

    content = json.loads(content_file.read_text())
    html = html_file.read_text()

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 72
    converter.single_line_break = False
    converter.unicode_snob = True

    body = converter.handle(html)

    # Clean up excessive blank lines (max 2 consecutive)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.strip()

    subject = content.get("subject_line", "")
    preview = content.get("preview_text", "")
    sources = content.get("sources", [])

    header = f"Subject: {subject}\nPreview: {preview}\n{'=' * 72}\n\n"

    sources_section = ""
    if sources:
        sources_section = "\n\n" + "=" * 72 + "\nSOURCES\n" + "=" * 72 + "\n"
        sources_section += "\n".join(f"- {url}" for url in sources)

    final = header + body + sources_section

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(final)
    print(f"Plain text version saved → {output_file}")
    print(f"  Length: {len(final):,} characters")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert newsletter HTML to plain text.")
    parser.add_argument("--html_file", default=str(HTML_FILE))
    parser.add_argument("--content_file", default=str(CONTENT_FILE))
    parser.add_argument("--output_file", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    run(Path(args.html_file), Path(args.content_file), Path(args.output_file))
