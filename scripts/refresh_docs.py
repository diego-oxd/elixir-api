#!/usr/bin/env python3
"""
scripts/refresh_docs.py

Pulls latest changes from each project's git repo and regenerates
documentation if there are new commits since the last generation.

Usage:
    python scripts/refresh_docs.py
    python scripts/refresh_docs.py --project-id <uuid>
    python scripts/refresh_docs.py --dry-run
    python scripts/refresh_docs.py --force
"""

import asyncio
import argparse
import subprocess
import logging
from pathlib import Path

# Add project root to path so app modules are importable
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import get_db, get_items, get_item_by_id, update_item
from app.routers.projects import _generate_documentation_with_claude_async

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def git_fetch(repo_path: str) -> bool:
    """Fetch remote tracking refs. Returns True on success."""
    result = subprocess.run(
        ["git", "fetch", "origin"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error(f"git fetch failed: {result.stderr}")
    return result.returncode == 0


def get_remote_commit(repo_path: str) -> str | None:
    """Return the latest commit hash on origin/HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", "origin/HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    # Fallback: ls-remote doesn't need a local branch pointer
    result = subprocess.run(
        ["git", "ls-remote", "origin", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout:
        return result.stdout.split()[0]
    return None


def git_pull(repo_path: str) -> bool:
    """Fast-forward the working tree. Returns True on success."""
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        logger.error(f"git pull failed: {result.stderr}")
    return result.returncode == 0


async def refresh_project(project: dict, dry_run: bool, force: bool) -> bool:
    """
    Refresh docs for a single project.
    Returns True if docs were regenerated, False if skipped or failed.
    """
    project_id = str(project["_id"])
    repo_path = project.get("repo_path")
    stored_commit = project.get("docs_last_commit")

    logger.info(f"[{project['name']}] Checking for updates at {repo_path}")

    if not repo_path or not Path(repo_path).exists():
        logger.warning(f"[{project['name']}] repo_path does not exist, skipping")
        return False

    if not git_fetch(repo_path):
        logger.error(f"[{project['name']}] fetch failed, skipping")
        return False

    remote_commit = get_remote_commit(repo_path)
    if remote_commit is None:
        logger.error(f"[{project['name']}] Could not determine remote commit, skipping")
        return False

    logger.info(f"[{project['name']}] stored={stored_commit or 'None'} remote={remote_commit[:8]}")

    needs_regen = force or (stored_commit != remote_commit)
    if not needs_regen:
        logger.info(f"[{project['name']}] Up to date, skipping")
        return False

    if dry_run:
        logger.info(f"[{project['name']}] [DRY RUN] Would regenerate docs")
        return False

    if not git_pull(repo_path):
        logger.error(f"[{project['name']}] pull failed, skipping")
        return False

    logger.info(f"[{project['name']}] Regenerating documentation...")
    try:
        with get_db() as db:
            await _generate_documentation_with_claude_async(
                project_id, repo_path, db, docs_commit=remote_commit
            )
        logger.info(f"[{project['name']}] Done. docs_last_commit -> {remote_commit[:8]}")
        return True
    except Exception as e:
        logger.error(f"[{project['name']}] Regeneration failed: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Refresh project documentation from latest repo commits"
    )
    parser.add_argument("--project-id", help="Only refresh this project ID")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check changes only, don't regenerate",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if commit unchanged",
    )
    args = parser.parse_args()

    with get_db() as db:
        if args.project_id:
            project = get_item_by_id(db, "projects", args.project_id)
            projects = [project] if project else []
        else:
            all_projects = get_items(db, "projects")
            projects = [p for p in all_projects if p.get("repo_url") and p.get("repo_path")]

    if not projects:
        logger.info("No projects with a linked repo found.")
        return

    logger.info(f"Found {len(projects)} project(s) to check")

    refreshed = 0
    for project in projects:
        ok = await refresh_project(project, dry_run=args.dry_run, force=args.force)
        if ok:
            refreshed += 1

    logger.info(f"Finished. {refreshed}/{len(projects)} project(s) had docs regenerated.")


if __name__ == "__main__":
    asyncio.run(main())
