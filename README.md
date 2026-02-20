# Job Search Agent

Automated daily pipeline that scrapes job listings, ranks them against your resume using an LLM, emails a digest of top matches, and tracks application status in Google Sheets. Runs on GitHub Actions (free).

## Pipeline

```
GitHub Actions (daily cron at 10 AM ET)
  1. SCRAPE  → JobSpy (LinkedIn, Indeed, Glassdoor) + company pages → raw_jobs.json
  2. DEDUP   → Filter previously seen jobs → new_jobs.json
  3. RANK    → LLM scores each job vs resume → ranked_jobs.json
  4. PUSH    → Email digest of top matches (SendGrid)
  5. TRACK   → Append to Google Sheet + update seen_jobs.json
```

## Requirements

- Python 3.11

## Setup

### 1. Set up Python environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you don't have Python 3.11, install it via [pyenv](https://github.com/pyenv/pyenv) or `brew install python@3.11`.

### 2. Add your resume

Place your resume as `resume.pdf`, `resume.docx`, or `resume.txt` in the project root.

### 3. Edit `config.yml`

- Set search keywords, location, job type preferences
- Choose your LLM provider (`claude`, `openai`, or `gemini`)
- Set your email address
- Add your Google Sheet ID
- Optionally add company career page URLs

### 4. Google Sheets setup

1. Create a Google Cloud project → enable Sheets API + Drive API
2. Create a Service Account → download the credentials JSON
3. Create a Google Sheet → share it with the service account email (Editor access)
4. Copy the sheet ID from the URL (`https://docs.google.com/spreadsheets/d/SHEET_ID/edit`)
5. Add the sheet ID to `config.yml`

### 5. GitHub Secrets

Add these secrets to your GitHub repo (Settings → Secrets → Actions):

| Secret | Required? | Notes |
|--------|-----------|-------|
| `ANTHROPIC_API_KEY` | If using Claude | ~$0.03/day |
| `OPENAI_API_KEY` | If using OpenAI | ~$0.02/day |
| `GOOGLE_API_KEY` | If using Gemini | Free tier |
| `SENDGRID_API_KEY` | Yes | 100 emails/day free |
| `GOOGLE_CREDENTIALS` | Yes | Service account JSON contents |
| `CONFIG_YML` | Yes | Paste full contents of your `config.yml` |

### 6. Deploy

Push to GitHub. The workflow runs daily at 10 AM ET, or trigger manually from Actions tab.

## Local testing

```bash
source .venv/bin/activate

# Run each step individually
python scripts/scrape.py
python scripts/dedup.py
python scripts/rank.py
python scripts/push.py --dry-run    # preview email without sending
python scripts/track.py
```

## Google Sheet structure

**Job Matches tab** (auto-populated):
| Date Found | Score | Title | Company | Location | Salary | Remote | Apply Link | Source | Key Matches | Status | Date Applied | Notes |

Update `Status` manually: `new` → `applied` → `interview` → `offer` / `rejected` / `passed`

**Stats tab** (auto-updated formulas): total jobs, applied count, interviews, offers, weekly count.
