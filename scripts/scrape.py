"""Step 1: Scrape job listings from multiple sources."""

import json
import os
import sys
from datetime import datetime

import httpx
import yaml
from bs4 import BeautifulSoup

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def load_config() -> dict:
    with open(os.path.join(PROJECT_ROOT, "config.yml"), "r") as f:
        return yaml.safe_load(f)


def scrape_jobspy(config: dict) -> list[dict]:
    """Scrape jobs using JobSpy (LinkedIn, Indeed, Glassdoor)."""
    from jobspy import scrape_jobs

    search = config["search"]
    all_jobs = []

    for keyword in search["keywords"]:
        print(f"Scraping for: {keyword}")
        try:
            df = scrape_jobs(
                site_name=["indeed", "linkedin", "glassdoor"],
                search_term=keyword,
                location=search.get("location", ""),
                distance=search.get("distance"),
                job_type=search.get("job_type"),
                is_remote=search.get("remote_only", False),
                results_wanted=search.get("results_per_source", 25),
                hours_old=search.get("hours_old", 24),
                country_indeed="USA",
            )
            print(f"  Found {len(df)} jobs for '{keyword}'")

            for _, row in df.iterrows():
                job = {
                    "title": str(row.get("title", "")),
                    "company": str(row.get("company_name", row.get("company", ""))),
                    "location": str(row.get("location", "")),
                    "description": str(row.get("description", "")),
                    "job_url": str(row.get("job_url", row.get("job_url_direct", ""))),
                    "date_posted": str(row.get("date_posted", "")),
                    "salary": _extract_salary(row),
                    "job_type": str(row.get("job_type", "")),
                    "is_remote": bool(row.get("is_remote", False)),
                    "source": str(row.get("site", "jobspy")),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                if job["job_url"] and job["title"]:
                    all_jobs.append(job)
        except Exception as e:
            print(f"  Error scraping '{keyword}': {e}", file=sys.stderr)

    return all_jobs


def _extract_salary(row) -> str:
    """Extract salary info from a JobSpy row."""
    parts = []
    min_sal = row.get("min_amount")
    max_sal = row.get("max_amount")
    currency = row.get("currency", "USD")
    interval = row.get("interval", "")
    if min_sal and str(min_sal) != "nan":
        parts.append(f"${int(float(min_sal)):,}")
    if max_sal and str(max_sal) != "nan":
        parts.append(f"${int(float(max_sal)):,}")
    salary = " - ".join(parts)
    if salary and interval:
        salary += f" / {interval}"
    return salary


def scrape_company_pages(config: dict) -> list[dict]:
    """Scrape jobs from custom company career pages."""
    pages = config.get("company_pages") or []
    all_jobs = []

    for page in pages:
        url = page["url"]
        company_name = page["name"]
        print(f"Scraping company page: {company_name} ({url})")

        try:
            resp = httpx.get(url, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for common job listing patterns
            job_links = []
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                href = a["href"]
                # Filter for links that look like job postings
                if len(text) > 10 and any(
                    kw in text.lower()
                    for kw in ["engineer", "developer", "manager", "analyst", "designer"]
                ):
                    if not href.startswith("http"):
                        href = url.rstrip("/") + "/" + href.lstrip("/")
                    job_links.append({"title": text, "url": href})

            for link in job_links:
                job = {
                    "title": link["title"],
                    "company": company_name,
                    "location": "",
                    "description": "",
                    "job_url": link["url"],
                    "date_posted": "",
                    "salary": "",
                    "job_type": "",
                    "is_remote": False,
                    "source": "company_page",
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                all_jobs.append(job)

            print(f"  Found {len(job_links)} potential jobs from {company_name}")
        except Exception as e:
            print(f"  Error scraping {company_name}: {e}", file=sys.stderr)

    return all_jobs


def deduplicate_by_url(jobs: list[dict]) -> list[dict]:
    """Remove duplicate jobs based on URL."""
    seen = set()
    unique = []
    for job in jobs:
        url = job.get("job_url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(job)
    return unique


def main():
    config = load_config()

    # Scrape from all sources
    jobspy_jobs = scrape_jobspy(config)
    company_jobs = scrape_company_pages(config)

    all_jobs = jobspy_jobs + company_jobs
    all_jobs = deduplicate_by_url(all_jobs)

    print(f"\nTotal unique jobs scraped: {len(all_jobs)}")

    # Save to data/raw_jobs.json
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = os.path.join(DATA_DIR, "raw_jobs.json")
    with open(output_path, "w") as f:
        json.dump(all_jobs, f, indent=2)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()