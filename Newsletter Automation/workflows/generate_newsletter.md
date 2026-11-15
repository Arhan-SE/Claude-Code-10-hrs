# Workflow: Generate Newsletter

## Objective
Given a topic, produce a polished HTML newsletter with infographics and send it via Gmail.

## One-Time Setup (do this before your first run)

1. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install MJML CLI**
   ```bash
   npm install -g mjml
   ```

3. **Fill in `.env`** — add these keys alongside the existing ones:
   ```
   TAVILY_API_KEY=tvly-...        # from tavily.com (free, 1k calls/month)
   FAL_KEY=...                    # from fal.ai (for nano-banana image generation)
   GMAIL_ADDRESS=you@gmail.com
   GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # from myaccount.google.com → Security → App passwords
   ```

4. **Fill in `brand-assets/brand.json`** with your real brand colors, name, and address.

5. **Add your logo** to `brand-assets/` as `logo.png` (or update `logo_filename` in brand.json).

---

## Inputs Required

| Input | Example |
|---|---|
| Topic | "The future of remote work in 2025" |
| Audience (optional) | "startup founders" — default: "general professional" |
| Tone (optional) | "conversational and bold" — default: "informative and engaging" |
| Sections (optional) | 5 — default: 4 |
| Recipients | email address(es) or path to a .txt file |

---

## Execution Steps

### Step 1 — Research
```bash
python tools/research_topic.py --topic "YOUR TOPIC HERE" --include_news
```
- Queries Tavily with advanced search + recent news
- Output: `.tmp/research_raw.json`
- If results look thin or off-topic, re-run with a more specific topic phrase

### Step 2 — Synthesize Content
```bash
python tools/synthesize_content.py --topic "YOUR TOPIC HERE"
```
- Sends research to GPT-4.1 to produce a fully structured newsletter JSON
- Output: `.tmp/content_structured.json`
- **You can hand-edit this file** before continuing to adjust headlines, body copy, section order, or infographic prompts without re-running research

Optional flags:
```bash
python tools/synthesize_content.py --topic "..." --audience "startup founders" --tone "conversational and bold" --sections 5
```

### Step 3 — Generate Infographics
```bash
python tools/generate_infographic.py
```
- For each section marked `dalle3`: calls Fal AI nano-banana model
- For each section marked `matplotlib`: renders a chart from data
- Sections marked `none`: skipped
- Output: `.tmp/infographics/section_01.png`, etc. + `manifest.json`
- **If a section's infographic fails**, the script logs a warning and continues — the newsletter still builds without that image

### Step 4 — Build HTML Newsletter
```bash
python tools/build_newsletter_html.py
```
- Compiles MJML template → HTML (via MJML CLI)
- Embeds infographics as base64 data URIs (no hosting needed)
- Inlines CSS with premailer
- Injects dark mode support
- Output: `.tmp/newsletter.html` + `.tmp/newsletter_preview.html`

Optional: pass `--color_scheme` to override the brand colors for this run:
```bash
python tools/build_newsletter_html.py --color_scheme warm-editorial
```
Available schemes: `professional-blue` (default), `warm-editorial`, `dark-tech`, `minimal-white`

### Step 5 — Generate Plain Text Version
```bash
python tools/convert_to_plaintext.py
```
- Output: `.tmp/newsletter_plain.txt`

### Step 6 — Review
```bash
open .tmp/newsletter_preview.html
```
Open in your browser. Check:
- [ ] Headline and intro read well
- [ ] All infographics loaded (no broken images)
- [ ] CTA button is correct
- [ ] Footer address is accurate
- [ ] Subject line looks compelling

If anything needs fixing, edit `.tmp/content_structured.json` and re-run from Step 4.

### Step 7 — Send

**Dry run first (always):**
```bash
python tools/send_newsletter.py --to "you@gmail.com" --dry_run
```

**Real send:**
```bash
python tools/send_newsletter.py --to "you@gmail.com,friend@example.com"
```

Or with a recipient list file:
```bash
python tools/send_newsletter.py --to recipients.txt
```

Send log saved to `.tmp/send_log.json`.

---

## Bonus Outputs

After Step 2, `.tmp/content_structured.json` also contains:
- **`social_snippet`** — ready-to-post 280-char social media post about the newsletter
- **`subject_line`** + **`preview_text`** — auto-used by the send tool

To retrieve the social snippet:
```bash
python -c "import json; d=json.load(open('.tmp/content_structured.json')); print(d['social_snippet'])"
```

---

## Error Reference

| Error | Cause | Fix |
|---|---|---|
| `mjml: command not found` | MJML CLI not installed | `npm install -g mjml` |
| `TAVILY_API_KEY not found` | Missing .env key | Sign up at tavily.com, add key to .env |
| `FAL_KEY not found` | Missing .env key | Sign up at fal.ai, add key to .env |
| `GMAIL_APP_PASSWORD` auth error | Wrong app password | Generate a new one at myaccount.google.com |
| Fal AI infographic fails | Rate limit or bad prompt | Script continues without that image; edit prompt in content_structured.json and re-run step 3 |
| Tavily low result count | Topic too niche | Use a broader or alternative phrasing for `--topic` |

---

## Re-running Individual Steps

The pipeline is modular. Each tool reads from and writes to specific `.tmp/` files, so you can re-run any step independently:

- Adjust copy only → edit `.tmp/content_structured.json`, re-run Steps 4–5
- Regenerate one infographic → edit the `infographic.prompt_or_data` in `content_structured.json`, re-run Step 3
- Change color scheme → re-run Step 4 with `--color_scheme`
- Resend to more recipients → re-run Step 7 only
