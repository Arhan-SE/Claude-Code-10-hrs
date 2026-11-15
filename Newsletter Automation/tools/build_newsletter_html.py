"""
build_newsletter_html.py

Compiles everything into a polished MJML-based HTML newsletter.

Steps:
1. Read content_structured.json + infographics manifest + brand-assets/brand.json
2. Base64-encode all infographic PNGs
3. Render an MJML template with all content and brand colors
4. Compile via MJML CLI (subprocess)
5. Post-process with premailer (CSS inlining)
6. Inject dark mode media query
7. Output newsletter.html + newsletter_preview.html (browser-viewable wrapper)

Prerequisites:
    npm install -g mjml

Usage:
    python tools/build_newsletter_html.py
    python tools/build_newsletter_html.py --color_scheme dark-tech
"""

import argparse
import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import premailer
from dotenv import load_dotenv

load_dotenv()

CONTENT_FILE = Path(".tmp/content_structured.json")
INFOGRAPHICS_DIR = Path(".tmp/infographics")
OUTPUT_FILE = Path(".tmp/newsletter.html")
PREVIEW_FILE = Path(".tmp/newsletter_preview.html")
BRAND_FILE = Path("brand-assets/brand.json")

COLOR_SCHEMES = {
    "professional-blue": {
        "primary": "#1a56db",
        "accent": "#e3efff",
        "background": "#f9fafb",
        "surface": "#ffffff",
        "text": "#111928",
        "muted": "#6b7280",
        "border": "#e5e7eb",
        "cta_bg": "#1a56db",
        "cta_text": "#ffffff",
    },
    "warm-editorial": {
        "primary": "#b45309",
        "accent": "#fef3c7",
        "background": "#fffbf5",
        "surface": "#ffffff",
        "text": "#1c1917",
        "muted": "#78716c",
        "border": "#e7e5e4",
        "cta_bg": "#b45309",
        "cta_text": "#ffffff",
    },
    "dark-tech": {
        "primary": "#7c3aed",
        "accent": "#ede9fe",
        "background": "#0f172a",
        "surface": "#1e293b",
        "text": "#f1f5f9",
        "muted": "#94a3b8",
        "border": "#334155",
        "cta_bg": "#7c3aed",
        "cta_text": "#ffffff",
    },
    "minimal-white": {
        "primary": "#111928",
        "accent": "#f3f4f6",
        "background": "#ffffff",
        "surface": "#ffffff",
        "text": "#111928",
        "muted": "#6b7280",
        "border": "#e5e7eb",
        "cta_bg": "#111928",
        "cta_text": "#ffffff",
    },
}


def load_brand(color_scheme: str) -> dict:
    """Load brand config, falling back to the chosen color scheme defaults."""
    scheme = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES["professional-blue"])

    if BRAND_FILE.exists():
        brand = json.loads(BRAND_FILE.read_text())
        # Brand colors override scheme if provided
        return {
            "primary": brand.get("primary_color", scheme["primary"]),
            "accent": brand.get("accent_color", scheme["accent"]),
            "background": brand.get("background_color", scheme["background"]),
            "surface": scheme["surface"],
            "text": brand.get("text_color", scheme["text"]),
            "muted": scheme["muted"],
            "border": scheme["border"],
            "cta_bg": brand.get("primary_color", scheme["cta_bg"]),
            "cta_text": scheme["cta_text"],
            "font_family": brand.get("font_family", "Inter, Arial, sans-serif"),
            "sender_name": brand.get("sender_name", "Newsletter"),
            "website_url": brand.get("website_url", "#"),
            "footer_address": brand.get("footer_address", "[Your Company Address]"),
            "logo_filename": brand.get("logo_filename", ""),
        }

    return {**scheme, "font_family": "Inter, Arial, sans-serif",
            "sender_name": "Newsletter", "website_url": "#",
            "footer_address": "[Your Company Address]", "logo_filename": ""}


def image_to_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def logo_data_uri(brand: dict) -> str | None:
    if not brand.get("logo_filename"):
        return None
    logo_path = Path("brand-assets") / brand["logo_filename"]
    if not logo_path.exists():
        return None
    data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    suffix = logo_path.suffix.lower().lstrip(".")
    mime = "svg+xml" if suffix == "svg" else suffix
    return f"data:image/{mime};base64,{data}"


def render_section_mjml(section: dict, index: int, manifest: dict, brand: dict) -> str:
    heading = section.get("heading", "")
    body = section.get("body", "").replace("\n", "<br/><br/>")
    key_stat = section.get("key_stat", "")
    infographic = manifest.get(str(index))

    image_block = ""
    if infographic and Path(infographic["file"]).exists():
        data_uri = image_to_data_uri(Path(infographic["file"]))
        caption = infographic.get("caption", "")
        image_block = f"""
    <mj-section padding="0 24px 8px">
      <mj-column>
        <mj-image src="{data_uri}" alt="{caption}" border-radius="8px" padding="0"/>
        {"<mj-text align='center' font-size='12px' color='" + brand['muted'] + "' padding='6px 0 0'>" + caption + "</mj-text>" if caption else ""}
      </mj-column>
    </mj-section>"""

    stat_block = ""
    if key_stat:
        stat_block = f"""
    <mj-section background-color="{brand['accent']}" border-radius="8px" padding="16px 24px" margin-bottom="16px">
      <mj-column>
        <mj-text font-size="16px" font-weight="600" color="{brand['primary']}" font-style="italic" padding="0">
          "{key_stat}"
        </mj-text>
      </mj-column>
    </mj-section>"""

    return f"""
    <mj-section padding="24px 24px 0">
      <mj-column>
        <mj-text font-size="20px" font-weight="700" color="{brand['text']}" padding="0 0 12px">
          {heading}
        </mj-text>
        <mj-text font-size="15px" color="{brand['text']}" line-height="1.7" padding="0">
          {body}
        </mj-text>
      </mj-column>
    </mj-section>
    {stat_block}
    {image_block}
    <mj-section padding="8px 24px 0">
      <mj-column>
        <mj-divider border-color="{brand['border']}" border-width="1px" padding="0"/>
      </mj-column>
    </mj-section>"""


def render_mjml(content: dict, manifest: dict, brand: dict) -> str:
    logo_uri = logo_data_uri(brand)
    logo_block = ""
    if logo_uri:
        logo_block = f'<mj-image src="{logo_uri}" width="120px" align="left" padding="0 0 8px"/>'

    sections_mjml = "\n".join(
        render_section_mjml(s, i, manifest, brand)
        for i, s in enumerate(content.get("sections", []))
    )

    intro = content.get("intro_paragraph", "").replace("\n", "<br/><br/>")
    conclusion = content.get("conclusion", "").replace("\n", "<br/><br/>")
    sources = content.get("sources", [])
    sources_html = "".join(
        f'<a href="{url}" style="color:{brand["primary"]};word-break:break-all;">{url}</a><br/>'
        for url in sources
    )

    return f"""<mjml>
  <mj-head>
    <mj-font name="Inter" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"/>
    <mj-attributes>
      <mj-all font-family="{brand['font_family']}"/>
      <mj-body background-color="{brand['background']}"/>
    </mj-attributes>
    <mj-style>
      a {{ color: {brand['primary']}; }}
      .dark-mode-bg {{ background-color: {brand['background']}; }}
    </mj-style>
  </mj-head>
  <mj-body background-color="{brand['background']}">

    <!-- Header -->
    <mj-section background-color="{brand['surface']}" padding="24px 24px 16px" border-bottom="3px solid {brand['primary']}">
      <mj-column>
        {logo_block}
        <mj-text font-size="13px" color="{brand['muted']}" padding="0">
          {brand['sender_name']}
        </mj-text>
      </mj-column>
    </mj-section>

    <!-- Hero -->
    <mj-section background-color="{brand['surface']}" padding="32px 24px 24px">
      <mj-column>
        <mj-text font-size="30px" font-weight="700" color="{brand['text']}" line-height="1.25" padding="0 0 16px">
          {content.get('headline', '')}
        </mj-text>
        <mj-text font-size="16px" color="{brand['muted']}" line-height="1.7" padding="0">
          {intro}
        </mj-text>
      </mj-column>
    </mj-section>

    <mj-section padding="0 24px">
      <mj-column>
        <mj-divider border-color="{brand['border']}" border-width="1px" padding="0"/>
      </mj-column>
    </mj-section>

    <!-- Content Sections -->
    {sections_mjml}

    <!-- Conclusion -->
    <mj-section background-color="{brand['surface']}" padding="32px 24px 24px">
      <mj-column>
        <mj-text font-size="15px" color="{brand['text']}" line-height="1.7" padding="0">
          {conclusion}
        </mj-text>
      </mj-column>
    </mj-section>

    <!-- CTA -->
    <mj-section background-color="{brand['accent']}" padding="32px 24px">
      <mj-column>
        <mj-button background-color="{brand['cta_bg']}" color="{brand['cta_text']}"
                   href="{content.get('cta_url', '#')}" border-radius="6px"
                   font-size="15px" font-weight="600" padding="14px 28px">
          {content.get('cta_text', 'Read More')}
        </mj-button>
      </mj-column>
    </mj-section>

    <!-- Sources -->
    <mj-section background-color="{brand['surface']}" padding="24px 24px 8px">
      <mj-column>
        <mj-text font-size="13px" font-weight="600" color="{brand['muted']}" padding="0 0 8px">
          SOURCES
        </mj-text>
        <mj-text font-size="12px" color="{brand['muted']}" line-height="1.8" padding="0">
          {sources_html}
        </mj-text>
      </mj-column>
    </mj-section>

    <!-- Footer -->
    <mj-section background-color="{brand['surface']}" padding="16px 24px 32px" border-top="1px solid {brand['border']}">
      <mj-column>
        <mj-text font-size="12px" color="{brand['muted']}" align="center" padding="0">
          {brand['sender_name']} · <a href="{brand['website_url']}">{brand['website_url']}</a>
          <br/>
          {brand['footer_address']}
          <br/>
          You received this email because you subscribed to {brand['sender_name']}.
          <a href="#">Unsubscribe</a>
        </mj-text>
      </mj-column>
    </mj-section>

  </mj-body>
</mjml>"""


def compile_mjml(mjml_source: str) -> str:
    """Write MJML to a temp file, compile with mjml CLI, return HTML string."""
    mjml_bin = shutil.which("mjml") or "./node_modules/.bin/mjml"
    if not shutil.which("mjml") and not Path("./node_modules/.bin/mjml").exists():
        raise RuntimeError(
            "mjml CLI not found. Install it with: npm install mjml"
        )

    with tempfile.NamedTemporaryFile(suffix=".mjml", mode="w", delete=False) as f:
        f.write(mjml_source)
        tmp_in = Path(f.name)

    tmp_out = tmp_in.with_suffix(".html")

    try:
        result = subprocess.run(
            [mjml_bin, str(tmp_in), "-o", str(tmp_out)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"MJML compilation failed:\n{result.stderr}")
        return tmp_out.read_text()
    finally:
        tmp_in.unlink(missing_ok=True)
        tmp_out.unlink(missing_ok=True)


def inject_dark_mode(html: str) -> str:
    dark_css = """
  <style>
    @media (prefers-color-scheme: dark) {{
      body, .mj-body {{ background-color: #0f172a !important; }}
      .mj-column-per-100 {{ background-color: #1e293b !important; }}
    }}
  </style>
  <meta name="color-scheme" content="light dark"/>"""
    return html.replace("</head>", dark_css + "\n</head>", 1)


def wrap_preview(html: str, subject: str) -> str:
    """Wrap the newsletter HTML in a centered browser-preview frame."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <title>Preview: {subject}</title>
  <style>
    body {{ margin: 0; padding: 20px; background: #e5e7eb; font-family: Arial, sans-serif; }}
    .preview-bar {{ max-width: 640px; margin: 0 auto 12px; padding: 10px 16px; background: #1f2937;
                    color: #f9fafb; border-radius: 8px 8px 0 0; font-size: 13px; }}
    .preview-bar strong {{ color: #60a5fa; }}
    .email-wrapper {{ max-width: 640px; margin: 0 auto; box-shadow: 0 4px 24px rgba(0,0,0,.2); border-radius: 0 0 8px 8px; overflow: hidden; }}
  </style>
</head>
<body>
  <div class="preview-bar">
    <strong>Subject:</strong> {subject}
  </div>
  <div class="email-wrapper">
    {html}
  </div>
</body>
</html>"""


def run(
    content_file: Path = CONTENT_FILE,
    infographics_dir: Path = INFOGRAPHICS_DIR,
    output_file: Path = OUTPUT_FILE,
    color_scheme: str = "professional-blue",
) -> None:
    if not content_file.exists():
        raise FileNotFoundError(f"{content_file} not found. Run synthesize_content.py first.")

    content = json.loads(content_file.read_text())
    brand = load_brand(color_scheme)

    manifest_path = infographics_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    print("Rendering MJML template...")
    mjml_source = render_mjml(content, manifest, brand)

    print("Compiling with MJML CLI...")
    html = compile_mjml(mjml_source)

    print("Inlining CSS with premailer...")
    html = premailer.transform(html, remove_classes=False, strip_important=False)

    print("Injecting dark mode support...")
    html = inject_dark_mode(html)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html)
    print(f"Newsletter HTML saved → {output_file}")

    preview_html = wrap_preview(html, content.get("subject_line", "Newsletter Preview"))
    PREVIEW_FILE.write_text(preview_html)
    print(f"Browser preview saved  → {PREVIEW_FILE}")
    print(f"\nOpen in browser: open {PREVIEW_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build newsletter HTML from structured content.")
    parser.add_argument("--content_file", default=str(CONTENT_FILE))
    parser.add_argument("--infographics_dir", default=str(INFOGRAPHICS_DIR))
    parser.add_argument("--output_file", default=str(OUTPUT_FILE))
    parser.add_argument("--color_scheme", default="professional-blue",
                        choices=list(COLOR_SCHEMES.keys()))
    args = parser.parse_args()

    run(Path(args.content_file), Path(args.infographics_dir),
        Path(args.output_file), args.color_scheme)
