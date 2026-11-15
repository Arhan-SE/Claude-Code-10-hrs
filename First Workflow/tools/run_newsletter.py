"""
run_newsletter.py — Main orchestrator for Align Lending newsletter automation.

Runs all three steps in sequence:
  1. fetch_news.py    — pull mortgage news from Tavily
  2. generate_newsletter.py — build branded HTML email via GPT-4o
  3. send_email.py    — deliver via Gmail SMTP

Usage:
  python tools/run_newsletter.py                  # Full run
  python tools/run_newsletter.py --dry-run        # Fetch + generate only (no send)
  python tools/run_newsletter.py --force          # Bypass 6-hour news cache
  python tools/run_newsletter.py --to me@email.com  # Override recipient
  python tools/run_newsletter.py --skip-fetch     # Use existing news_data.json
"""

import argparse
import sys
import time
from pathlib import Path

# Add tools/ to path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).parent))

import fetch_news
import generate_newsletter
import send_email


def print_banner(step: int, name: str):
    print()
    print(f"{'━' * 50}")
    print(f"  STEP {step}: {name}")
    print(f"{'━' * 50}")


def run_step(step_num: int, name: str, fn, *args, **kwargs):
    print_banner(step_num, name)
    start = time.time()
    try:
        fn(*args, **kwargs)
    except SystemExit as e:
        # fetch/generate/send call sys.exit(1) on errors — re-raise cleanly
        elapsed = time.time() - start
        print(f"\n✗ Step '{name}' failed after {elapsed:.1f}s (exit code {e.code})")
        sys.exit(e.code)
    elapsed = time.time() - start
    print(f"\n✓ Step '{name}' completed in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="Generate and send the Align Lending weekly mortgage newsletter"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and generate newsletter but do NOT send the email",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the 6-hour Tavily cache and re-fetch news",
    )
    parser.add_argument(
        "--to",
        metavar="EMAIL",
        help="Override the RECIPIENT_EMAIL from .env",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip fetch step and use existing .tmp/news_data.json",
    )
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║    Align Lending — Newsletter Automation         ║")
    print("╚══════════════════════════════════════════════════╝")

    if args.dry_run:
        print("  Mode: DRY RUN (email will NOT be sent)")
    if args.skip_fetch:
        print("  Skipping fetch step (using cached news_data.json)")

    # ── Step 1: Fetch News ─────────────────────────────────
    if not args.skip_fetch:
        run_step(1, "Fetch Mortgage News (Tavily)", fetch_news.main, force=args.force)
    else:
        print_banner(1, "Fetch Mortgage News (Tavily) — SKIPPED")

    # ── Step 2: Generate Newsletter HTML ──────────────────
    run_step(2, "Generate Newsletter HTML (GPT-4o)", generate_newsletter.main)

    # ── Step 3: Send Email ────────────────────────────────
    if args.dry_run:
        print_banner(3, "Send Email (Gmail) — SKIPPED (dry-run)")
        preview_path = Path(__file__).parent.parent / ".tmp" / "newsletter.html"
        print(f"\n  Preview your newsletter:")
        print(f"  open '{preview_path}'")
    else:
        run_step(3, "Send Email (Gmail)", send_email.main, recipient_override=args.to)

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║    All steps complete!                           ║")
    print("╚══════════════════════════════════════════════════╝")

    if args.dry_run:
        print("\n  Dry run complete. Open .tmp/newsletter.html to preview.")
    else:
        recipient = args.to or __import__("os").getenv("RECIPIENT_EMAIL", "")
        print(f"\n  Newsletter delivered to: {recipient}")


if __name__ == "__main__":
    main()
