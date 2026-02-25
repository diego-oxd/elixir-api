#!/usr/bin/env python3
"""Generate code quality metrics for a local repository.

Usage:
    # Print metrics as JSON (no DB access)
    uv run python scripts/generate_metrics.py <repo_path>

    # Save to database
    uv run python scripts/generate_metrics.py <repo_path> --project-id <uuid> --save
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.services.metrics import run_metrics, save_metrics  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Generate code quality metrics for a local repository"
    )
    parser.add_argument("repo_path", help="Path to the repository to analyse")
    parser.add_argument("--project-id", help="Project UUID (required with --save)")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Persist results to the database (requires --project-id and DATABASE_URL)",
    )
    args = parser.parse_args()

    if args.save and not args.project_id:
        print("Error: --project-id is required when using --save", file=sys.stderr)
        sys.exit(1)

    project_id = args.project_id or ""

    print(f"Analysing: {args.repo_path}", file=sys.stderr)
    snapshot = run_metrics(args.repo_path, project_id)

    print(json.dumps(snapshot.model_dump(mode="json"), indent=2, default=str))

    if args.save:
        from app.db import get_db

        with get_db() as db:
            save_metrics(db, project_id, snapshot)
        print(f"\nSaved metrics for project {project_id}", file=sys.stderr)


if __name__ == "__main__":
    main()
