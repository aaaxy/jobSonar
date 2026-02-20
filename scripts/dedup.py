"""Step 2: Filter out previously seen jobs using Google Sheets."""

import json
import os

from sheets import get_gspread_client, get_seen_urls, get_spreadsheet, load_config

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def fetch_seen_urls_from_sheet() -> set[str]:
    """Fetch seen job URLs from Google Sheets.

    Returns an empty set (all jobs treated as new) if credentials are missing,
    sheet is unconfigured, or the API is unreachable.
    """
    try:
        config = load_config()
        gc = get_gspread_client()
        if gc is None:
            return set()

        spreadsheet = get_spreadsheet(gc, config)
        if spreadsheet is None:
            return set()

        urls = get_seen_urls(spreadsheet, config)
        print(f"Fetched {len(urls)} seen URLs from Google Sheets.")
        return urls
    except Exception as e:
        print(f"Warning: Could not fetch seen URLs from Google Sheets: {e}")
        print("All jobs will be treated as new.")
        return set()


def main():
    raw_path = os.path.join(DATA_DIR, "raw_jobs.json")
    new_path = os.path.join(DATA_DIR, "new_jobs.json")

    # Load raw jobs
    with open(raw_path, "r") as f:
        raw_jobs = json.load(f)
    print(f"Raw jobs loaded: {len(raw_jobs)}")

    # Fetch seen URLs from Google Sheets
    seen_urls = fetch_seen_urls_from_sheet()
    print(f"Previously seen jobs: {len(seen_urls)}")

    # Filter out seen jobs
    new_jobs = [
        job for job in raw_jobs if job.get("job_url", "") not in seen_urls
    ]

    print(f"New jobs after dedup: {len(new_jobs)}")

    # Save new jobs
    with open(new_path, "w") as f:
        json.dump(new_jobs, f, indent=2)
    print(f"Saved to {new_path}")


if __name__ == "__main__":
    main()
