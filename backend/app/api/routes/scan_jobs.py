from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlmodel import Session

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import ScanJob, User
from app.worker import get_queue

router = APIRouter(prefix="/scan-jobs", tags=["scan-jobs"]) 


class ScanJobCreate(BaseModel):
    url: HttpUrl


class ScanJobEnqueued(BaseModel):
    id: str
    status: str
    next: str


class ScanJobStatus(BaseModel):
    id: str
    status: str  # pending | processing | done | failed
    error: str | None = None
    teaser: dict | None = None
    # extra fields (optional for clients that want them)
    progress: int | None = None


# ---- Routes ----

@router.post("", response_model=ScanJobEnqueued, summary="Start scan (enqueue only)")
def start_scan(
    payload: ScanJobCreate,
    db: SessionDep,
    user=None,
):
    """Create a scan job row and enqueue background processing. Return immediately (<200ms)."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        job = ScanJob(
            url=str(payload.url),
            status="pending",  # stable external state
            progress=0,
            owner_id=getattr(user, "id", None),
            teaser_json=None,
            full_json=None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"Created scan job {job.id} for URL: {payload.url}")

        # Enqueue background task (best-effort; do not fail the request on queue errors)
        try:
            q = get_queue()
            # Pass kwargs explicitly; avoid colliding with RQ's job_id parameter
            q.enqueue(
                "app.worker.process_scan_job",
                kwargs={"job_id": str(job.id), "url": str(payload.url), "user_id": (getattr(user, "id", None))},
                job_timeout="15m",
            )
            logger.info(f"Enqueued job {job.id} to worker queue")
        except Exception as e:
            logger.error(f"Failed to enqueue job {job.id}: {e}")

        return ScanJobEnqueued(id=str(job.id), status=job.status, next=f"/api/v1/scan-jobs/{job.id}/status")
    except Exception as e:
        logger.error(f"Failed to create scan job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create scan job: {str(e)}")


@router.get("/{job_id}/status", response_model=ScanJobStatus)
def get_status(job_id: str, db: SessionDep):
    job = db.get(ScanJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    # Map internal statuses to stable external states
    raw = (job.status or "").lower()
    if raw in ("queued", "pending", "idle", "queued", "teaser_ready"):
        ext = "pending"
    elif raw in ("running", "processing", "crawl", "parse", "analyze", "generate"):
        ext = "processing"
    elif raw in ("done", "full_ready"):
        ext = "done"
    elif raw.startswith("error") or raw in ("failed", "error"):
        ext = "failed"
    else:
        ext = "pending"

    # Derive a minimal teaser
    teaser_src = job.teaser_json or {}
    minimal_teaser = None
    if teaser_src:
        minimal_teaser = {
            "title": teaser_src.get("title"),
            "schema_count": (1 if teaser_src.get("has_schema") else 0),
            "has_schema": bool(teaser_src.get("has_schema")),
        }

    # Error message (if any)
    error_msg = None
    try:
        if isinstance(job.full_json, dict):
            error_msg = job.full_json.get("error")
    except Exception:
        error_msg = None

    return ScanJobStatus(
        id=str(job.id),
        status=ext,
        error=error_msg,
        teaser=minimal_teaser,
        progress=job.progress or 0,
    )


@router.get("/{job_id}/full")
def get_full(job_id: str, db: SessionDep):
    job = db.get(ScanJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if job.status != "done" or not job.full_json:
        raise HTTPException(status_code=425, detail="Scan not ready")
    return job.full_json
