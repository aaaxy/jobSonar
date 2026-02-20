"""Step 4: Format and send email digest of top-ranked jobs."""

import argparse
import json
import os
from datetime import datetime

import yaml
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")


def load_config() -> dict:
    with open(os.path.join(PROJECT_ROOT, "config.yml"), "r") as f:
        return yaml.safe_load(f)


def render_email(jobs: list[dict], config: dict) -> str:
    """Render the HTML email digest from the template."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("email_digest.html")

    min_score = config.get("scoring", {}).get("min_score", 60)
    above_min = [j for j in jobs if j.get("score", 0) >= min_score]
    top_n = config.get("email", {}).get("top_n", 20)
    display_jobs = above_min[:top_n]

    # Top 5 with reasoning
    top_reasonings = [
        {
            "title": j["title"],
            "company": j["company"],
            "score": j["score"],
            "reasoning": j.get("reasoning", ""),
            "key_matches": j.get("key_matches", []),
        }
        for j in display_jobs[:5]
        if j.get("reasoning")
    ]

    html = template.render(
        date=datetime.utcnow().strftime("%B %d, %Y"),
        total_new=len(jobs),
        total_above_min=len(above_min),
        shown_count=len(display_jobs),
        min_score=min_score,
        jobs=display_jobs,
        top_reasonings=top_reasonings,
        sheet_id=config.get("google_sheets", {}).get("sheet_id", ""),
    )
    return html


def send_email(html: str, config: dict):
    """Send the email digest via SendGrid."""
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Content, Email, Mail, To

    email_config = config["email"]
    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])

    message = Mail(
        from_email=Email(email_config["from"]),
        to_emails=To(email_config["to"]),
        subject=f"Job Digest - {datetime.utcnow().strftime('%B %d, %Y')}",
        html_content=Content("text/html", html),
    )

    response = sg.send(message)
    print(f"Email sent! Status: {response.status_code}")


def main():
    parser = argparse.ArgumentParser(description="Send job digest email")
    parser.add_argument("--dry-run", action="store_true", help="Print email to console instead of sending")
    args = parser.parse_args()

    config = load_config()

    # Load ranked jobs
    ranked_path = os.path.join(DATA_DIR, "ranked_jobs.json")
    with open(ranked_path, "r") as f:
        ranked_jobs = json.load(f)

    if not ranked_jobs:
        print("No ranked jobs found. Skipping email.")
        return

    min_score = config.get("scoring", {}).get("min_score", 60)
    above_min = [j for j in ranked_jobs if j.get("score", 0) >= min_score]
    if not above_min:
        print(f"No jobs scored above {min_score}. Skipping email.")
        return

    # Render email
    html = render_email(ranked_jobs, config)

    if args.dry_run:
        print("=== DRY RUN - Email Preview ===")
        print(f"To: {config['email']['to']}")
        print(f"From: {config['email']['from']}")
        print(f"Subject: Job Digest - {datetime.utcnow().strftime('%B %d, %Y')}")
        print(f"Jobs above min score: {len(above_min)}")
        print("=" * 50)
        # Write HTML to file for preview
        preview_path = os.path.join(DATA_DIR, "email_preview.html")
        with open(preview_path, "w") as f:
            f.write(html)
        print(f"HTML preview saved to {preview_path}")
    else:
        send_email(html, config)


if __name__ == "__main__":
    main()
