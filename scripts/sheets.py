"""Shared Google Sheets authentication and helpers."""

import json
import os

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config() -> dict:
    """Load config.yml from project root."""
    with open(os.path.join(PROJECT_ROOT, "config.yml"), "r") as f:
        return yaml.safe_load(f)


def get_gspread_client():
    """Authenticate with Google Sheets via GOOGLE_CREDENTIALS env var.

    Returns a gspread.Client or None if credentials are unavailable.
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        print("GOOGLE_CREDENTIALS not set. Skipping Google Sheets access.")
        return None

    creds_dict = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def get_spreadsheet(gc, config):
    """Open the Google Sheet by ID from config.

    Returns the spreadsheet object or None if unconfigured.
    """
    sheets_config = config.get("google_sheets", {})
    sheet_id = sheets_config.get("sheet_id")
    if not sheet_id or sheet_id == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("Google Sheet ID not configured. Skipping Google Sheets access.")
        return None

    return gc.open_by_key(sheet_id)


def get_seen_urls(spreadsheet, config) -> set[str]:
    """Fetch all Apply Link URLs (column H) from the Job Matches tab.

    Returns a set of URL strings.
    """
    import gspread

    sheets_config = config.get("google_sheets", {})
    tab_name = sheets_config.get("job_matches_tab", "Job Matches")

    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return set()

    try:
        apply_link_col = 8  # column H
        urls = worksheet.col_values(apply_link_col)[1:]  # skip header
        return set(url for url in urls if url)
    except Exception:
        return set()
