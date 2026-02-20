"""Step 2: Filter out previously seen jobs."""

import hashlib
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def url_hash(url: str) -> str:
    """Create a short hash of a URL for dedup storage."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def load_seen_jobs(path: str) -> dict:
    """Load the seen jobs database."""
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def main():
    raw_path = os.path.join(DATA_DIR, "raw_jobs.json")
    seen_path = os.path.join(DATA_DIR, "seen_jobs.json")
    new_path = os.path.join(DATA_DIR, "new_jobs.json")

    # Load raw jobs
    with open(raw_path, "r") as f:
        raw_jobs = json.load(f)
    print(f"Raw jobs loaded: {len(raw_jobs)}")

    # Load seen jobs
    seen = load_seen_jobs(seen_path)
    seen_hashes = set(seen.keys())
    print(f"Previously seen jobs: {len(seen_hashes)}")

    # Filter out seen jobs
    new_jobs = []
    for job in raw_jobs:
        h = url_hash(job.get("job_url", ""))
        if h not in seen_hashes:
            new_jobs.append(job)

    print(f"New jobs after dedup: {len(new_jobs)}")

    # Save new jobs
    with open(new_path, "w") as f:
        json.dump(new_jobs, f, indent=2)
    print(f"Saved to {new_path}")


if __name__ == "__main__":
    main()
