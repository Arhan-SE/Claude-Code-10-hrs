"""
send_newsletter.py

Sends the newsletter via Gmail using smtplib + a Gmail App Password.

Images are sent as inline CID attachments (not base64 data URIs) because
Gmail strips data: URI images. The HTML src="data:..." values are replaced
with src="cid:imageN" and the images are attached as inline MIME parts.

Required .env keys:
    GMAIL_ADDRESS       your Gmail address
    GMAIL_APP_PASSWORD  app password from myaccount.google.com → Security → App passwords

Usage:
    python tools/send_newsletter.py --to you@example.com --dry_run
    python tools/send_newsletter.py --to you@example.com,friend@example.com
    python tools/send_newsletter.py --to recipients.txt
"""

import argparse
import base64
import json
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CONTENT_FILE = Path(".tmp/content_structured.json")
HTML_FILE = Path(".tmp/newsletter.html")
TEXT_FILE = Path(".tmp/newsletter_plain.txt")
LOG_FILE = Path(".tmp/send_log.json")
BRAND_FILE = Path("brand-assets/brand.json")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def load_recipients(to_arg: str) -> list[str]:
    if to_arg.endswith(".txt") and Path(to_arg).exists():
        lines = Path(to_arg).read_text().splitlines()
        return [line.strip() for line in lines if line.strip() and "@" in line]
    return [e.strip() for e in to_arg.split(",") if e.strip()]


def load_sender_name() -> str:
    if BRAND_FILE.exists():
        brand = json.loads(BRAND_FILE.read_text())
        return brand.get("sender_name", "Newsletter")
    return "Newsletter"


def extract_inline_images(html: str) -> tuple[str, list[dict]]:
    """
    Find all data: URI images in the HTML, replace with cid: references,
    and return the modified HTML plus a list of image dicts with CID and bytes.
    """
    images = []
    counter = [0]

    def replace_data_uri(match):
        full_src = match.group(1)
        # Parse mime type and base64 data
        m = re.match(r"data:(image/\w+);base64,(.+)", full_src)
        if not m:
            return match.group(0)
        mime_type = m.group(1)          # e.g. "image/png"
        b64_data = m.group(2)
        img_bytes = base64.b64decode(b64_data)
        cid = f"image{counter[0]}"
        counter[0] += 1
        images.append({"cid": cid, "mime_type": mime_type, "data": img_bytes})
        return f'src="cid:{cid}"'

    modified_html = re.sub(r'src="(data:image[^"]+)"', replace_data_uri, html)
    return modified_html, images


def build_message(subject: str, sender_name: str, gmail_address: str,
                  recipient: str, html_body: str, text_body: str,
                  preview_text: str) -> MIMEMultipart:
    """
    Build a multipart/mixed email with:
      - plain text alternative
      - HTML with inline CID images (multipart/related)
    """
    # Inject invisible preheader for preview text
    preheader = (
        f'<span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">'
        f'{preview_text}</span>'
    )
    html_with_preheader = html_body.replace("<body", preheader + "<body", 1)

    # Extract base64 images and replace with CID refs
    html_cid, inline_images = extract_inline_images(html_with_preheader)

    # Build structure: multipart/mixed > multipart/alternative > (plain, multipart/related > (html, images))
    msg_mixed = MIMEMultipart("mixed")
    msg_mixed["Subject"] = subject
    msg_mixed["From"] = f"{sender_name} <{gmail_address}>"
    msg_mixed["To"] = recipient

    msg_alternative = MIMEMultipart("alternative")

    # Plain text part
    msg_alternative.attach(MIMEText(text_body, "plain", "utf-8"))

    if inline_images:
        # HTML + images in a related container
        msg_related = MIMEMultipart("related")
        msg_related.attach(MIMEText(html_cid, "html", "utf-8"))

        for img in inline_images:
            subtype = img["mime_type"].split("/")[1]
            mime_img = MIMEImage(img["data"], _subtype=subtype)
            mime_img.add_header("Content-ID", f"<{img['cid']}>")
            mime_img.add_header("Content-Disposition", "inline", filename=f"{img['cid']}.{subtype}")
            msg_related.attach(mime_img)

        msg_alternative.attach(msg_related)
    else:
        msg_alternative.attach(MIMEText(html_cid, "html", "utf-8"))

    msg_mixed.attach(msg_alternative)
    return msg_mixed


def run(to_arg: str, dry_run: bool = False) -> None:
    for path in (CONTENT_FILE, HTML_FILE, TEXT_FILE):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run the full pipeline first."
            )

    gmail_address = os.environ.get("GMAIL_ADDRESS", "")
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_address or not app_password:
        raise EnvironmentError(
            "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env"
        )

    content = json.loads(CONTENT_FILE.read_text())
    subject = content.get("subject_line", "Newsletter")
    preview_text = content.get("preview_text", "")
    html_body = HTML_FILE.read_text()
    text_body = TEXT_FILE.read_text()
    sender_name = load_sender_name()
    recipients = load_recipients(to_arg)

    if not recipients:
        raise ValueError("No valid recipient email addresses found.")

    # Count images for reporting
    _, inline_images_preview = extract_inline_images(html_body)

    print(f"\nNewsletter: {subject}")
    print(f"From:       {sender_name} <{gmail_address}>")
    print(f"To:         {', '.join(recipients)}")
    print(f"Images:     {len(inline_images_preview)} inline CID attachment(s)")
    print(f"Dry run:    {dry_run}")

    if dry_run:
        print("\n[DRY RUN] Email payload ready. Not sending.")
        print(f"  HTML size:  {len(html_body):,} chars")
        print(f"  Text size:  {len(text_body):,} chars")
        print(f"  Recipients: {len(recipients)}")
        print("\nRun without --dry_run to send.")
        return

    log_entries = []
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(gmail_address, app_password)
        print("\nConnected to Gmail SMTP. Sending...")

        for recipient in recipients:
            msg = build_message(subject, sender_name, gmail_address,
                                recipient, html_body, text_body, preview_text)
            try:
                server.sendmail(gmail_address, recipient, msg.as_string())
                print(f"  Sent → {recipient}")
                log_entries.append({
                    "recipient": recipient,
                    "status": "sent",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                print(f"  FAILED → {recipient}: {e}")
                log_entries.append({
                    "recipient": recipient,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps({
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "results": log_entries,
    }, indent=2))

    sent = sum(1 for e in log_entries if e["status"] == "sent")
    failed = len(log_entries) - sent
    print(f"\nDone. Sent: {sent}, Failed: {failed}")
    print(f"Log saved → {LOG_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send newsletter via Gmail.")
    parser.add_argument("--to", required=True,
                        help="Comma-separated emails or path to .txt file with one email per line")
    parser.add_argument("--dry_run", action="store_true",
                        help="Print payload without sending")
    args = parser.parse_args()

    run(args.to, args.dry_run)
