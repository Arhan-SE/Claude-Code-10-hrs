"""
send_email.py — Gmail SMTP sender for Align Lending newsletter.

Reads .tmp/newsletter.html and sends it via Gmail SMTP using an app password.
"""

import argparse
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

INPUT_PATH = Path(__file__).parent.parent / ".tmp" / "newsletter.html"


def load_html() -> str:
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found. Run generate_newsletter.py first.")
        sys.exit(1)
    return INPUT_PATH.read_text(encoding="utf-8")


def build_subject() -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    return f"Align Lending | AGI Intelligence Briefing — {date_str}"


def build_plain_text() -> str:
    return (
        "This email is best viewed in an HTML-capable email client.\n\n"
        "Visit us at https://alignlending.com for the latest mortgage news and rates.\n\n"
        "— Align Lending Newsletter\n"
        "info@alignlending.com\n\n"
        "To unsubscribe, reply with 'Unsubscribe' in the subject line."
    )


def build_message(html: str, sender: str, recipient: str) -> MIMEMultipart:
    subject = build_subject()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Align Lending Newsletter <{sender}>"
    msg["To"] = recipient

    # Plain-text fallback (required for spam compliance)
    plain_part = MIMEText(build_plain_text(), "plain", "utf-8")
    msg.attach(plain_part)

    # HTML part (shown in modern clients)
    html_part = MIMEText(html, "html", "utf-8")
    msg.attach(html_part)

    return msg


def send(msg: MIMEMultipart, sender: str, password: str):
    # Gmail app passwords may include spaces — strip them
    password = password.replace(" ", "")

    print(f"[send_email] Connecting to smtp.gmail.com:465...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(sender, password)
            server.sendmail(sender, msg["To"], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed.")
        print("Make sure you are using an App Password (not your regular password).")
        print("Generate one at: https://myaccount.google.com/apppasswords")
        print("(Requires 2-Step Verification to be enabled on your Gmail account.)")
        sys.exit(1)
    except smtplib.SMTPRecipientsRefused:
        print(f"ERROR: Recipient address refused: {msg['To']}")
        print("Check RECIPIENT_EMAIL in your .env file.")
        sys.exit(1)
    except TimeoutError:
        print("ERROR: Connection to Gmail SMTP timed out.")
        print("Check your internet connection and firewall settings.")
        sys.exit(1)


def main(recipient_override: str | None = None):
    sender = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = recipient_override or os.getenv("RECIPIENT_EMAIL")

    if not sender:
        print("ERROR: GMAIL_ADDRESS not set in .env")
        sys.exit(1)
    if not password:
        print("ERROR: GMAIL_APP_PASSWORD not set in .env")
        print("Generate one at: https://myaccount.google.com/apppasswords")
        sys.exit(1)
    if not recipient:
        print("ERROR: RECIPIENT_EMAIL not set in .env (or --to not provided)")
        sys.exit(1)

    print("[send_email] Loading newsletter HTML...")
    html = load_html()
    print(f"  HTML size: {len(html) // 1024}KB")

    msg = build_message(html, sender, recipient)
    subject = msg["Subject"]

    send(msg, sender, password)

    print(f"[send_email] Email sent successfully!")
    print(f"  To:      {recipient}")
    print(f"  Subject: {subject}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send Align Lending newsletter via Gmail")
    parser.add_argument("--to", metavar="EMAIL", help="Override recipient email address")
    args = parser.parse_args()
    main(recipient_override=args.to)
