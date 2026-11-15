# Newsletter Automation — Align Lending

## Objective
Generate and send a branded weekly mortgage market newsletter to a recipient email address.
The newsletter pulls live mortgage/housing news, generates a styled HTML email with rate snapshots, story cards, and a CTA, then delivers it via Gmail.

---

## Required Inputs

All secrets live in `.env` (never committed to git):

| Key | Description |
|---|---|
| `TAVILY_API_KEY` | Tavily search API key — get at https://app.tavily.com |
| `OPENAI_API_KEY` | OpenAI API key — get at https://platform.openai.com/api-keys |
| `FAL_KEY` | Fal.ai API key for infographic generation — get at https://fal.ai/dashboard/keys |
| `GMAIL_ADDRESS` | The Gmail account to send from (e.g. you@gmail.com) |
| `GMAIL_APP_PASSWORD` | Gmail App Password (NOT your regular password — see setup below) |
| `RECIPIENT_EMAIL` | The address to deliver the newsletter to |

---

## Gmail App Password Setup
1. Enable 2-Step Verification on your Google account: https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Select app: **Mail**, device: give it a name (e.g. "Newsletter Bot")
4. Copy the 16-character password into `GMAIL_APP_PASSWORD` in `.env`
5. Spaces in the password are fine — the script strips them automatically

---

## How to Run

### Install dependencies (first time only)
```bash
pip install -r requirements.txt
```

### Full run (fetch → generate → send)
```bash
python tools/run_newsletter.py
```

### Preview only (no email sent)
```bash
python tools/run_newsletter.py --dry-run
# Then open .tmp/newsletter.html in your browser to inspect
open .tmp/newsletter.html
```

### Force re-fetch (bypass 6-hour cache)
```bash
python tools/run_newsletter.py --force
```

### Send to a different address (testing)
```bash
python tools/run_newsletter.py --to test@example.com
```

### Run individual steps
```bash
python tools/fetch_news.py           # Step 1 only
python tools/generate_newsletter.py  # Step 2 only (requires news_data.json)
python tools/send_email.py           # Step 3 only (requires newsletter.html)
```

---

## Tools Used

| Step | Script | API | Purpose |
|---|---|---|---|
| 1 | `tools/fetch_news.py` | Tavily | Fetch mortgage/housing news |
| 2a | `tools/generate_infographics.py` | Fal.ai nano-banana | Generate rate + market infographic images |
| 2b | `tools/generate_newsletter.py` | OpenAI GPT-4o | Generate branded HTML email with injected infographics |
| 3 | `tools/send_email.py` | Gmail SMTP | Deliver email |
| — | `tools/run_newsletter.py` | — | Orchestrates all steps |

---

## Expected Outputs

| File | Description |
|---|---|
| `.tmp/news_data.json` | Raw Tavily results + rate hints (cached 6h) |
| `.tmp/newsletter.html` | Generated HTML email (open in browser to preview) |
| Delivered email | HTML newsletter in recipient's inbox |

---

## Email Structure

1. **Header** — Red bar with Align Lending logo, date, tagline
2. **Rate Snapshot** — 3 stat boxes: 30-Yr Fixed, 15-Yr Fixed, Fed Funds Rate (with ▲/▼ indicators)
3. **This Week in Mortgages** — 3–4 story cards with headlines (linked), 2-sentence summaries, source labels
4. **Market Insight** — Actionable callout with red left border + "Talk to a Loan Officer" CTA button
5. **Quick Tip** — One practical tip for homeowners or buyers
6. **Footer** — Contact info, legal disclaimer, unsubscribe link

---

## API Limits & Costs

| Service | Limit | Impact |
|---|---|---|
| Tavily (free tier) | 1,000 searches/month | 5 searches per run = ~200 runs/month max |
| Fal.ai nano-banana | Pay-per-use | ~$0.039 per image × 2 = ~$0.08 per newsletter run |
| OpenAI GPT-4o | Pay-per-use | ~$0.01–0.02 per newsletter run |
| Gmail free SMTP | 500 sends/day | Sufficient for personal use; use SendGrid/Mailchimp at scale |

---

## Error Handling

| Error | Cause | Fix |
|---|---|---|
| `TAVILY_API_KEY not set` | Missing env key | Add key to `.env` |
| `Fewer than 3 articles returned` | Tavily quota or bad queries | Check quota at app.tavily.com; retry with `--force` |
| `OPENAI_API_KEY not set` | Missing env key | Add key to `.env` |
| `HTML appears truncated` | GPT-4o token limit hit | Usually re-running fixes it; check OpenAI dashboard for errors |
| `Gmail authentication failed` | Wrong password type | Use App Password, not regular Gmail password |
| `SMTPRecipientsRefused` | Bad recipient address | Check `RECIPIENT_EMAIL` in `.env` |
| `Connection timed out` | Network/firewall issue | Check internet; port 465 must be open |

---

## Scheduling (Optional)

To run the newsletter automatically on a schedule, use the system's cron or the Claude Code `CronCreate` tool.

Example: send every Monday at 8am
```bash
# crontab -e
0 8 * * 1 cd /path/to/project && python tools/run_newsletter.py >> .tmp/newsletter.log 2>&1
```

---

## Infographic Generation (Fal.ai Nano-Banana)

The newsletter includes 2 AI-generated infographic images embedded inline as base64 JPEGs:

1. **Rate Snapshot infographic** — placed below the Rate Snapshot heading; shows a styled rate dashboard
2. **Market Insight infographic** — placed above the Market Insight callout; shows a housing market trend visual

**How it works:**
- GPT-4o generates HTML with placeholder comments `<!-- FAL_INFOGRAPHIC_RATES -->` and `<!-- FAL_INFOGRAPHIC_MARKET -->`
- `generate_infographics.py` calls `fal-ai/nano-banana` with custom prompts tuned to the day's rate data and news headlines
- Images are downloaded and base64-encoded as JPEG data URIs
- Placeholders are replaced with `<img>` tags post-generation

**If fal.ai fails:** Infographic generation failures are non-blocking — the newsletter generates without images rather than crashing.

---

## Known Constraints & Notes

- **Logo embedding**: The logo is base64-encoded inline in the HTML (~112KB). This keeps the email self-contained but means large logo files will bloat the email. Keep `brand-assets/logo.png` under 200KB.
- **Outlook compatibility**: The email uses MSO-compatible table layout. Rate snapshot boxes use a `<table>` structure that renders correctly in Outlook 2016+.
- **Scaling**: For a real subscriber list, replace Gmail SMTP with SendGrid, Mailchimp, or AWS SES. Gmail's daily limit is 500 sends.
- **Rate numbers**: Extracted from Tavily result snippets via regex. If no numbers are found, GPT-4o uses its best estimate and marks them as approximate. Always verify before sending to a live list.
- **Content freshness**: Tavily results cache for 6 hours. For a weekly newsletter, always run with `--force` to ensure fresh content.
