"""
TFAH Dashboard — FastAPI backend with REST + SSE endpoints.
"""

import asyncio
import os
import subprocess
import signal
import sys

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from dashboard.backend.models import (
    get_incident,
    get_incident_stats,
    get_pipeline_events,
    get_recent_timeline,
    init_db,
    list_incidents,
)
from dashboard.backend.sse import broadcaster
from dashboard.backend.triggers import (
    run_full_pipeline,
    trigger_classify,
    trigger_codegen,
    trigger_crash,
    trigger_notify,
    trigger_pr,
)

# ── App ───────────────────────────────────────────────────────

app = FastAPI(title="TFAH Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()


# ── SSE endpoint ──────────────────────────────────────────────

@app.get("/api/events")
async def sse_events():
    async def event_stream():
        async for msg in broadcaster.subscribe():
            yield msg
    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Stats ─────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    return get_incident_stats()


@app.get("/api/timeline")
def timeline(days: int = 7):
    return get_recent_timeline(days)


# ── Incidents ─────────────────────────────────────────────────

@app.get("/api/incidents")
def incidents_list(limit: int = 50, offset: int = 0, status: str | None = None, fault_type: str | None = None):
    return list_incidents(limit=limit, offset=offset, status=status, fault_type=fault_type)


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: int):
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    events = get_pipeline_events(incident_id)
    return {**incident, "events": events}


# ── Trigger: Full Pipeline ────────────────────────────────────

class PipelineRunRequest(BaseModel):
    crash_log: str | None = None


@app.post("/api/pipeline/run")
async def pipeline_run(req: PipelineRunRequest, background_tasks: BackgroundTasks):
    async def _run():
        try:
            await run_full_pipeline(crash_log=req.crash_log)
        except Exception:
            pass  # errors already recorded in DB
    background_tasks.add_task(_run)
    return {"status": "started"}


@app.post("/api/pipeline/replay/{incident_id}")
async def pipeline_replay(incident_id: int, background_tasks: BackgroundTasks):
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")

    async def _run():
        try:
            await run_full_pipeline(crash_log=incident["crash_log"])
        except Exception:
            pass
    background_tasks.add_task(_run)
    return {"status": "replaying", "source_incident_id": incident_id}


# ── Trigger: Individual Steps ─────────────────────────────────

@app.post("/api/trigger/crash")
async def api_trigger_crash():
    crash_log = await trigger_crash()
    return {"crash_log": crash_log}


class ClassifyRequest(BaseModel):
    incident_id: int
    crash_log: str


@app.post("/api/trigger/classify")
async def api_trigger_classify(req: ClassifyRequest):
    result = await trigger_classify(req.incident_id, req.crash_log)
    return result


class CodegenRequest(BaseModel):
    incident_id: int
    source_code: str
    fault_type: str
    action: str
    summary: str


@app.post("/api/trigger/codegen")
async def api_trigger_codegen(req: CodegenRequest):
    result = await trigger_codegen(
        req.incident_id, req.source_code, req.fault_type, req.action, req.summary
    )
    return {"changes_summary": result["changes_summary"]}


class PRRequest(BaseModel):
    incident_id: int
    push: bool = True  # Manual trigger defaults to pushing + opening PR


@app.post("/api/trigger/pr")
async def api_trigger_pr(req: PRRequest):
    incident = get_incident(req.incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    if not incident.get("fixed_code"):
        raise HTTPException(400, "No generated fix found. Run codegen first.")
    try:
        result = await trigger_pr(
            req.incident_id,
            incident["fixed_code"],
            incident["test_code"],
            incident["incident_report"],
            incident["fault_type"],
            incident["source_file_path"],
            push=req.push,
            existing_branch=incident.get("branch_name"),
        )
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))


class NotifyRequest(BaseModel):
    incident_id: int


@app.post("/api/trigger/notify")
async def api_trigger_notify(req: NotifyRequest):
    incident = get_incident(req.incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    await trigger_notify(
        req.incident_id,
        incident["fault_type"] or "unknown",
        incident["action"] or "none",
        incident["confidence"] or 0.0,
        incident["summary"] or "",
        incident.get("pr_url", "pending"),
    )
    return {"notified": True}


# ── Mock Server Management ────────────────────────────────────

_mock_server_proc: subprocess.Popen | None = None


@app.post("/api/mock-server/start")
async def start_mock_server():
    global _mock_server_proc
    if _mock_server_proc and _mock_server_proc.poll() is None:
        return {"status": "already_running", "pid": _mock_server_proc.pid}
    _mock_server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mock_server.server:app", "--port", "8429"],
        cwd=PROJECT_ROOT,
    )
    return {"status": "started", "pid": _mock_server_proc.pid}


@app.post("/api/mock-server/stop")
async def stop_mock_server():
    global _mock_server_proc
    if _mock_server_proc and _mock_server_proc.poll() is None:
        _mock_server_proc.send_signal(signal.SIGTERM)
        _mock_server_proc.wait(timeout=5)
        _mock_server_proc = None
        return {"status": "stopped"}
    return {"status": "not_running"}


@app.get("/api/mock-server/status")
async def mock_server_status():
    if _mock_server_proc and _mock_server_proc.poll() is None:
        return {"status": "running", "pid": _mock_server_proc.pid}
    return {"status": "stopped"}


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
