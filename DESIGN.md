# Job Search Agent — Design Document

## Overview

A daily automated pipeline that scrapes job listings, ranks them against a resume using an LLM, emails a digest of top matches, and tracks application status. Runs on GitHub Actions (free tier).

---

## Architecture

```
GitHub Actions (daily cron)
  │
  ├─ 1. SCRAPE ──→ JobSpy (LinkedIn, Indeed, Glassdoor) + company career pages
  │                 Output: data/raw_jobs.json
  │
  ├─ 2. DEDUP ───→ Filter out previously seen jobs (data/seen_jobs.json)
  │                 Output: data/new_jobs.json
  │
  ├─ 3. RANK ────→ LLM scores each job vs resume (Claude / OpenAI / Gemini)
  │                 Output: data/ranked_jobs.json
  │
  ├─ 4. PUSH ────→ Format top N jobs → send email digest (SendGrid)
  │                 Output: email sent
  │
  └─ 5. TRACK ───→ Append ranked jobs to Google Sheet + update seen_jobs.json
                    User edits status/notes directly in Google Sheets
```

---

## Step 1: Scrape (`scripts/scrape.py`)

### JobSpy integration

[JobSpy](https://github.com/speedyapply/JobSpy) scrapes LinkedIn, Indeed, and Glassdoor concurrently. It returns a structured pandas DataFrame with: title, company, location, description, job_url, date_posted, salary, job_type, is_remote.

Searches are driven by `config.yml`:
- Multiple keywords (each searched independently across all sources)
- Location + distance radius
- Job type filter (fulltime, parttime, etc.)
- Remote-only toggle
- Results per source cap
- Recency filter (`hours_old`: only jobs posted within N hours)

### Company career pages

Users can list specific company career page URLs in `config.yml`. These are scraped with `httpx` + BeautifulSoup. The scraper looks for anchor tags containing job-related keywords (engineer, developer, etc.) and normalizes them to the same schema as JobSpy results.

This is a best-effort approach — career pages vary widely in structure. For companies with non-standard pages, users may need to add custom parsing logic.

### Output

All results are deduplicated by URL within the run and written to `data/raw_jobs.json`.

---

## Step 2: Dedup (`scripts/dedup.py`)

- Loads `data/seen_jobs.json` — a dictionary mapping URL hashes to metadata (title, company, date first seen)
- URL hashes use SHA-256 truncated to 16 hex chars
- Any scraped job whose URL hash is already in the set is filtered out
- Only genuinely new jobs proceed to the ranking step
- This prevents wasting LLM API calls on already-scored jobs and prevents the same listing from appearing in multiple daily digests

### Output

`data/new_jobs.json` — only jobs not previously seen.

---

## Step 3: Rank (`scripts/rank.py`)

### Multi-LLM support

Uses [litellm](https://github.com/BerriAI/litellm) as a unified interface. The user selects provider and model in `config.yml`:

| Provider | Model | Approx. cost (50 jobs/day) |
|----------|-------|-----------------------------|
| Claude   | claude-haiku-4-5-20251001 | ~$0.01–0.03 |
| OpenAI   | gpt-4o-mini | ~$0.01–0.02 |
| Gemini   | gemini-2.0-flash | ~$0.01 (generous free tier) |

Only one LLM API key is required (whichever provider is selected).

### Scoring approach

1. `resume_parser.py` extracts text from the user's resume (PDF via PyMuPDF, DOCX via python-docx, or plain text)
2. Jobs are sent to the LLM in configurable batches (default: 5 per call) to reduce API round-trips
3. The prompt asks for a JSON response per job containing:
   - `score` (0–100): overall relevance to the candidate
   - `reasoning` (1–2 sentences): why this score
   - `key_matches` (list): specific skills/qualifications that matched
4. Scoring criteria: skills match, experience level alignment, industry relevance, role responsibilities match
5. Results are sorted by score descending and filtered by `min_score` (default: 60)

### Error handling

If the LLM response fails to parse as JSON or the API call errors, the batch receives a default score of 50 with a "Scoring failed" note, so the pipeline continues.

### Output

`data/ranked_jobs.json` — all scored jobs (including below-threshold ones, for tracking purposes).

---

## Step 4: Push (`scripts/push.py`)

### Email delivery

Uses [SendGrid](https://sendgrid.com/) (free tier: 100 emails/day).

### Email content

Rendered from `templates/email_digest.html` using Jinja2:
- **Header**: date and summary stats ("Found 15 new jobs, 8 scored above 60")
- **Table**: Score (color-coded) | Title | Company | Location | Salary | Apply button
- **Top 5 reasoning**: detailed cards explaining why the highest-scored jobs matched
- **Footer**: link to the Google Sheet for application tracking

### Score color coding

- Green (>=80): strong match
- Orange (>=60): moderate match
- Red (<60): weak match

### Dry run mode

`python scripts/push.py --dry-run` prints metadata to console and saves the rendered HTML to `data/email_preview.html` for local preview, without sending any email.

---

## Step 5: Track (`scripts/track.py`)

### Google Sheets (primary user-facing storage)

Uses `gspread` + Google Service Account (free).

**Tab 1: "Job Matches"** — auto-populated by the pipeline:

| Date Found | Score | Title | Company | Location | Salary | Remote | Apply Link | Source | Key Matches | Status | Date Applied | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

- Pipeline appends new ranked jobs (above `min_score`) daily
- User manually updates `Status` and `Notes` columns
- Status flow: `new` → `applied` → `interview` → `offer` / `rejected` / `passed`

**Tab 2: "Stats"** — auto-updated with COUNTIF/COUNTIFS formulas:

| Metric | Value |
|---|---|
| Total jobs found | (formula) |
| Applied | (formula) |
| Interviews | (formula) |
| Offers | (formula) |
| Rejected | (formula) |
| Passed | (formula) |
| This week's new jobs | (formula) |
| Average score | (formula) |

Both tabs are auto-created with headers and formulas if they don't exist.

### Dedup storage (`data/seen_jobs.json`)

- JSON dictionary: `{url_hash: {title, company, date_seen}}`
- Committed to the repo by the GitHub Actions workflow after each run
- Serves as the fast local dedup layer (Step 2) to avoid wasting LLM calls
- Google Sheets is the source of truth for tracking; `track.py` also checks the sheet before appending to handle edge cases

---

## GitHub Actions Workflow

`.github/workflows/daily_search.yml`:
- **Schedule**: `0 14 * * *` (10 AM ET daily)
- **Manual trigger**: `workflow_dispatch` for testing
- **Steps**: checkout → setup Python 3.11 → install deps → write `config.yml` from `CONFIG_YML` secret → run all 5 pipeline scripts sequentially → commit & push updated `data/` files
- `config.yml` is gitignored (contains personal info); the workflow writes it at runtime from a GitHub Secret
- Scripts run in order with env vars injected from GitHub Secrets

---

## Dependencies

| Package | Purpose |
|---------|---------|
| python-jobspy | Job scraping (LinkedIn, Indeed, Glassdoor) |
| litellm | Unified LLM interface (Claude, OpenAI, Gemini) |
| pymupdf | PDF resume parsing |
| python-docx | DOCX resume parsing |
| sendgrid | Email delivery |
| jinja2 | Email templating |
| pyyaml | Config parsing |
| httpx | HTTP client for company career pages |
| beautifulsoup4 | HTML parsing for company pages |
| gspread | Google Sheets API client |
| google-auth | Google service account authentication |

---

## API Keys & Secrets

| Secret | Required? | Free tier? |
|--------|-----------|------------|
| `ANTHROPIC_API_KEY` | If using Claude | Pay-as-you-go (~$0.03/day) |
| `OPENAI_API_KEY` | If using OpenAI | Pay-as-you-go (~$0.02/day) |
| `GOOGLE_API_KEY` | If using Gemini | Generous free tier |
| `SENDGRID_API_KEY` | Yes | 100 emails/day free |
| `GOOGLE_CREDENTIALS` | Yes | Free (service account JSON) |
| `CONFIG_YML` | Yes | Full contents of `config.yml` |

---

## Testing & Verification

1. **Manual trigger**: Run `workflow_dispatch` from GitHub Actions UI to test the full pipeline
2. **Local testing**: Each script runs independently:
   - `python scripts/scrape.py` → verify `data/raw_jobs.json` has results
   - `python scripts/dedup.py` → verify `data/new_jobs.json` filters correctly
   - `python scripts/rank.py` → verify `data/ranked_jobs.json` has scores
   - `python scripts/push.py --dry-run` → preview email HTML without sending
   - `python scripts/track.py` → verify Google Sheet is updated
3. **End-to-end**: Trigger the GitHub Action, verify email arrives with ranked jobs and working apply links

---

## Design Decisions

### Why JobSpy over direct API scraping?
JobSpy handles the complexity of scraping multiple job boards (anti-bot measures, pagination, varying HTML structures) behind a clean API. It's actively maintained and returns structured data.

### Why litellm over direct SDK calls?
litellm provides a unified `completion()` interface across Claude, OpenAI, and Gemini. Users can switch providers by changing one line in config without any code changes. It also handles retries and error normalization.

### Why Google Sheets over a database?
Google Sheets is user-facing, editable from any device, requires no infrastructure, and is free. Users can update application status, add notes, and share with others without touching code. The Stats tab provides a live dashboard with built-in formulas.

### Why SHA-256 URL hashes for dedup?
URL strings can be long and messy. A truncated hash (16 hex chars) provides a compact, collision-resistant key for the dedup dictionary while keeping `seen_jobs.json` small.

### Why batch scoring?
Sending 5 jobs per LLM call instead of 1 reduces API round-trips by 5x, cutting both latency and per-request overhead costs. The batch size is configurable if response quality degrades with larger batches.

### Why SendGrid over SMTP?
SendGrid's free tier (100 emails/day) is more than sufficient. It provides HTML email rendering, delivery tracking, and doesn't require configuring SMTP credentials. The `--dry-run` flag allows local testing without an account.
