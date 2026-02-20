"""Step 3: LLM-based relevance scoring of jobs against resume."""

import json
import os
import sys

import yaml
from litellm import completion

from resume_parser import extract_resume_text, find_resume

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

SCORING_PROMPT = """You are a job relevance scorer. Given a candidate's resume and a batch of job postings, rate each job's relevance to the candidate on a scale of 0-100.

Consider:
- Skills match (technical skills, tools, languages)
- Experience level alignment
- Industry/domain relevance
- Role responsibilities match

For each job, return a JSON object with: score (0-100), reasoning (1-2 sentences), key_matches (list of matching skills/qualifications).

RESUME:
{resume_text}

JOB POSTINGS:
{jobs_text}

Return a JSON array with one entry per job, in the same order as presented:
[
  {{"job_index": 0, "score": <int>, "reasoning": "<string>", "key_matches": ["skill1", "skill2"]}},
  ...
]

Return ONLY the JSON array, no other text."""


def load_config() -> dict:
    with open(os.path.join(PROJECT_ROOT, "config.yml"), "r") as f:
        return yaml.safe_load(f)


def format_job_for_prompt(index: int, job: dict) -> str:
    """Format a single job for the LLM prompt."""
    parts = [f"--- Job {index} ---"]
    parts.append(f"Title: {job.get('title', 'N/A')}")
    parts.append(f"Company: {job.get('company', 'N/A')}")
    parts.append(f"Location: {job.get('location', 'N/A')}")
    if job.get("salary"):
        parts.append(f"Salary: {job['salary']}")
    if job.get("job_type"):
        parts.append(f"Type: {job['job_type']}")
    desc = job.get("description", "")
    if desc:
        # Truncate long descriptions to save tokens
        parts.append(f"Description: {desc[:2000]}")
    return "\n".join(parts)


def score_batch(jobs: list[dict], resume_text: str, config: dict) -> list[dict]:
    """Score a batch of jobs using the configured LLM."""
    llm_config = config["llm"]
    provider = llm_config["provider"]
    model = llm_config["model"]

    # Build the model string for litellm
    model_map = {
        "claude": f"anthropic/{model}",
        "openai": model,
        "gemini": f"gemini/{model}",
    }
    litellm_model = model_map.get(provider, model)

    # Format jobs for prompt
    jobs_text = "\n\n".join(
        format_job_for_prompt(i, job) for i, job in enumerate(jobs)
    )

    prompt = SCORING_PROMPT.format(resume_text=resume_text, jobs_text=jobs_text)

    try:
        response = completion(
            model=litellm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,
        )
        content = response.choices[0].message.content.strip()

        # Parse JSON response - handle markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        scores = json.loads(content)
        return scores
    except json.JSONDecodeError as e:
        print(f"  Failed to parse LLM response as JSON: {e}", file=sys.stderr)
        print(f"  Response: {content[:500]}", file=sys.stderr)
        # Return default scores
        return [
            {"job_index": i, "score": 50, "reasoning": "Scoring failed", "key_matches": []}
            for i in range(len(jobs))
        ]
    except Exception as e:
        print(f"  LLM API error: {e}", file=sys.stderr)
        return [
            {"job_index": i, "score": 50, "reasoning": "Scoring failed", "key_matches": []}
            for i in range(len(jobs))
        ]


def main():
    config = load_config()
    scoring_config = config.get("scoring", {})
    min_score = scoring_config.get("min_score", 60)
    batch_size = scoring_config.get("batch_size", 5)

    # Load new jobs
    new_path = os.path.join(DATA_DIR, "new_jobs.json")
    with open(new_path, "r") as f:
        new_jobs = json.load(f)
    print(f"Jobs to score: {len(new_jobs)}")

    if not new_jobs:
        print("No new jobs to score.")
        with open(os.path.join(DATA_DIR, "ranked_jobs.json"), "w") as f:
            json.dump([], f)
        return

    # Load resume
    resume_path = find_resume(PROJECT_ROOT)
    resume_text = extract_resume_text(resume_path)
    print(f"Resume loaded: {len(resume_text)} chars")

    # Score in batches
    all_scored = []
    for i in range(0, len(new_jobs), batch_size):
        batch = new_jobs[i : i + batch_size]
        print(f"Scoring batch {i // batch_size + 1} ({len(batch)} jobs)...")

        scores = score_batch(batch, resume_text, config)

        for score_data in scores:
            idx = score_data.get("job_index", 0)
            if idx < len(batch):
                job = batch[idx].copy()
                job["score"] = score_data.get("score", 0)
                job["reasoning"] = score_data.get("reasoning", "")
                job["key_matches"] = score_data.get("key_matches", [])
                all_scored.append(job)

    # Sort by score descending
    all_scored.sort(key=lambda j: j.get("score", 0), reverse=True)

    # Filter by minimum score
    above_min = [j for j in all_scored if j.get("score", 0) >= min_score]
    print(f"\nTotal scored: {len(all_scored)}")
    print(f"Above min score ({min_score}): {len(above_min)}")

    # Save all scored jobs (not just above min, for tracking)
    output_path = os.path.join(DATA_DIR, "ranked_jobs.json")
    with open(output_path, "w") as f:
        json.dump(all_scored, f, indent=2)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
