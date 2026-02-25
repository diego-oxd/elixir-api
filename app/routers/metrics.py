from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.db import PostgresDatabase, get_db_dependency, get_item_by_id
from app.services.metrics import generate_metrics

router = APIRouter(prefix="/projects", tags=["metrics"])


@router.post("/{project_id}/generate-metrics")
def trigger_generate_metrics(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    project = get_item_by_id(db, "projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    repo_path = project.get("repo_path")
    if not repo_path:
        raise HTTPException(status_code=400, detail="Project has no repository path")

    background_tasks.add_task(generate_metrics, project_id, repo_path, db)
    return {"status": "started", "message": "Metrics generation started in background"}
