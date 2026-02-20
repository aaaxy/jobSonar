"""Step 5: Append ranked jobs to Google Sheet."""

import json
import os
from datetime import datetime

from sheets import get_gspread_client, get_spreadsheet, load_config

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def append_to_google_sheet(ranked_jobs: list[dict], config: dict):
    """Append ranked jobs to the Google Sheet."""
    import gspread

    gc = get_gspread_client()
    if gc is None:
        return

    spreadsheet = get_spreadsheet(gc, config)
    if spreadsheet is None:
        return

    sheets_config = config.get("google_sheets", {})
    tab_name = sheets_config.get("job_matches_tab", "Job Matches")

    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        # Create the worksheet with headers
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=13)
        headers = [
            "Date Found", "Score", "Title", "Company", "Location",
            "Salary", "Remote", "Apply Link", "Source", "Key Matches",
            "Status", "Date Applied", "Notes",
        ]
        worksheet.append_row(headers)
        print(f"Created '{tab_name}' tab with headers.")

    # Get existing URLs to avoid duplicates
    try:
        apply_link_col = 8  # column H
        existing_urls = set(worksheet.col_values(apply_link_col)[1:])  # skip header
    except Exception:
        existing_urls = set()

    # Prepare new rows
    today = datetime.utcnow().strftime("%Y-%m-%d")
    min_score = config.get("scoring", {}).get("min_score", 60)
    new_rows = []

    for job in ranked_jobs:
        if job.get("job_url") in existing_urls:
            continue
        if job.get("score", 0) < min_score:
            continue
        row = [
            today,
            job.get("score", 0),
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("salary", ""),
            "Yes" if job.get("is_remote") else "No",
            job.get("job_url", ""),
            job.get("source", ""),
            ", ".join(job.get("key_matches", [])),
            "new",
            "",
            "",
        ]
        new_rows.append(row)

    if new_rows:
        worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"Appended {len(new_rows)} new jobs to Google Sheet.")
    else:
        print("No new jobs to append to Google Sheet.")

    # Update stats tab
    _update_stats_tab(spreadsheet, sheets_config)


def _update_stats_tab(spreadsheet, sheets_config: dict):
    """Create or update the Stats tab with summary formulas."""
    stats_tab_name = sheets_config.get("stats_tab", "Stats")
    job_tab_name = sheets_config.get("job_matches_tab", "Job Matches")

    try:
        stats_ws = spreadsheet.worksheet(stats_tab_name)
    except Exception:
        stats_ws = spreadsheet.add_worksheet(title=stats_tab_name, rows=20, cols=2)

    # Set up stats with formulas referencing the Job Matches tab
    stats_data = [
        ["Metric", "Value"],
        ["Total jobs found", f"=COUNTA('{job_tab_name}'!C2:C)"],
        ["Applied", f"=COUNTIF('{job_tab_name}'!K:K,\"applied\")"],
        ["Interviews", f"=COUNTIF('{job_tab_name}'!K:K,\"interview\")"],
        ["Offers", f"=COUNTIF('{job_tab_name}'!K:K,\"offer\")"],
        ["Rejected", f"=COUNTIF('{job_tab_name}'!K:K,\"rejected\")"],
        ["Passed", f"=COUNTIF('{job_tab_name}'!K:K,\"passed\")"],
        [
            "This week's new jobs",
            f"=COUNTIFS('{job_tab_name}'!A:A,\">=\"&(TODAY()-7),'{job_tab_name}'!A:A,\"<=\"&TODAY())",
        ],
        ["Average score", f"=IFERROR(AVERAGE('{job_tab_name}'!B2:B),0)"],
    ]

    stats_ws.update("A1", stats_data, value_input_option="USER_ENTERED")
    print("Stats tab updated.")


def main():
    config = load_config()

    # Load ranked jobs
    ranked_path = os.path.join(DATA_DIR, "ranked_jobs.json")
    if not os.path.exists(ranked_path):
        print("No ranked_jobs.json found. Nothing to track.")
        return

    with open(ranked_path, "r") as f:
        ranked_jobs = json.load(f)

    if not ranked_jobs:
        print("No ranked jobs to track.")
        return

    print(f"Tracking {len(ranked_jobs)} ranked jobs...")

    # Update Google Sheet
    append_to_google_sheet(ranked_jobs, config)


if __name__ == "__main__":
    main()
