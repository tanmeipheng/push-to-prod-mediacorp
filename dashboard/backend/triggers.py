"""
Pipeline triggers — wrappers around existing TFAH modules
that integrate with the dashboard's incident tracking and SSE.
"""

import asyncio
import os
import sys
import traceback

# Ensure the project root is on sys.path so we can import agent/crash_runner/etc.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard.backend.models import (
    add_pipeline_event,
    create_incident,
    update_incident,
)
from dashboard.backend.sse import broadcaster


async def _emit(incident_id: int, node: str, event_type: str, data: dict | None = None):
    payload = {"incident_id": incident_id, "node": node}
    if data:
        payload.update(data)
    add_pipeline_event(incident_id, node, event_type, data)
    await broadcaster.broadcast(f"node_{event_type}", payload)


async def trigger_crash() -> str:
    """Run the crash runner and return the crash log."""
    from crash_runner.run_and_capture import run_and_capture
    loop = asyncio.get_event_loop()
    crash_log = await loop.run_in_executor(None, run_and_capture)
    return crash_log


async def trigger_classify(incident_id: int, crash_log: str) -> dict:
    """Classify a crash log and update the incident."""
    from agent.router import classify_fault

    await _emit(incident_id, "classify", "start")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, classify_fault, crash_log)
        update_incident(
            incident_id,
            fault_type=result["fault_type"],
            http_status=result.get("http_status"),
            action=result["action"],
            confidence=result["confidence"],
            summary=result["summary"],
        )
        await _emit(incident_id, "classify", "done", result)
        return result
    except Exception as e:
        await _emit(incident_id, "classify", "error", {"error": str(e)})
        update_incident(incident_id, status="error", error_message=str(e))
        raise


async def trigger_codegen(incident_id: int, source_code: str, fault_type: str, action: str, summary: str) -> dict:
    """Generate fix + test code and update the incident."""
    from agent.coder import generate_fix

    await _emit(incident_id, "codegen", "start")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, generate_fix, source_code, fault_type, action, summary
        )

        from agent.prompts import INCIDENT_REPORT_TEMPLATE

        incident_report = INCIDENT_REPORT_TEMPLATE.format(
            fault_type=fault_type,
            http_status="N/A",
            confidence=0.0,
            action=action,
            summary=summary,
            changes_summary=result["changes_summary"],
        )

        update_incident(
            incident_id,
            fixed_code=result["fixed_code"],
            test_code=result["test_code"],
            changes_summary=result["changes_summary"],
            incident_report=incident_report,
        )
        await _emit(incident_id, "codegen", "done", {"changes_summary": result["changes_summary"]})
        return result
    except Exception as e:
        await _emit(incident_id, "codegen", "error", {"error": str(e)})
        update_incident(incident_id, status="error", error_message=str(e))
        raise


async def trigger_pr(incident_id: int, fixed_code: str, test_code: str, incident_report: str, fault_type: str, source_file_path: str, push: bool | None = None, existing_branch: str | None = None) -> dict:
    """Create branch + PR and update the incident.

    Args:
        push: If None, reads TFAH_PUSH_TO_REMOTE env var. If True/False, overrides.
        existing_branch: If set, skip branch creation and push this branch directly.
    """
    from automator.github_pr import create_and_push_pr, push_existing_branch_and_pr

    await _emit(incident_id, "open_pr", "start")
    try:
        if push is None:
            should_push = os.environ.get("TFAH_PUSH_TO_REMOTE", "false").lower() == "true"
        else:
            should_push = push

        loop = asyncio.get_event_loop()

        # If a branch already exists (from a prior pipeline run), just push + PR it
        if existing_branch and should_push:
            pr_url = await loop.run_in_executor(
                None,
                push_existing_branch_and_pr,
                existing_branch, fault_type, incident_report or "",
            )
            branch_name = existing_branch
        else:
            branch_name, pr_url = await loop.run_in_executor(
                None,
                create_and_push_pr,
                fixed_code, test_code, incident_report or "", fault_type,
                source_file_path, should_push,
            )

        update_incident(
            incident_id,
            branch_name=branch_name,
            pr_url=pr_url or f"local:{branch_name}",
        )
        await _emit(incident_id, "open_pr", "done", {"branch_name": branch_name, "pr_url": pr_url or f"local:{branch_name}"})
        return {"branch_name": branch_name, "pr_url": pr_url}
    except Exception as e:
        error_detail = traceback.format_exc()
        await _emit(incident_id, "open_pr", "error", {"error": error_detail})
        update_incident(incident_id, status="error", error_message=error_detail)
        raise


async def trigger_notify(incident_id: int, fault_type: str, action: str, confidence: float, summary: str, pr_url: str) -> None:
    """Send Slack notification and update the incident."""
    from notifier.slack_webhook import send_triage_alert

    await _emit(incident_id, "notify", "start")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, send_triage_alert, fault_type, action, confidence, summary, pr_url,
        )
        update_incident(incident_id, notified=1)
        await _emit(incident_id, "notify", "done", {"notified": True})
    except Exception as e:
        await _emit(incident_id, "notify", "error", {"error": str(e)})
        # Non-fatal — don't mark entire incident as error
        raise


async def run_full_pipeline(crash_log: str | None = None) -> int:
    """Run the complete TFAH pipeline with dashboard tracking."""
    # Step 1: Crash
    if not crash_log:
        crash_log = await trigger_crash()

    # Read source code
    source_path = os.path.join(PROJECT_ROOT, "vulnerable_app", "integration.py")
    with open(source_path) as f:
        source_code = f.read()

    source_file_path = "vulnerable_app/integration.py"
    incident_id = create_incident(crash_log, source_code, source_file_path)
    await broadcaster.broadcast("pipeline_start", {"incident_id": incident_id})

    try:
        # Step 2: Classify
        classification = await trigger_classify(incident_id, crash_log)

        if classification["fault_type"] == "unknown":
            update_incident(incident_id, status="skipped")
            await _emit(incident_id, "classify", "skip", {"reason": "Non-transient fault"})
            await broadcaster.broadcast("pipeline_done", {"incident_id": incident_id, "status": "skipped"})
            return incident_id

        # Step 3: Codegen
        codegen_result = await trigger_codegen(
            incident_id, source_code,
            classification["fault_type"],
            classification["action"],
            classification["summary"],
        )

        # Read updated incident to get full data
        from dashboard.backend.models import get_incident
        incident = get_incident(incident_id)

        # Step 4: PR (push=True so it actually creates the PR on GitHub)
        await trigger_pr(
            incident_id,
            codegen_result["fixed_code"],
            codegen_result["test_code"],
            incident["incident_report"],
            classification["fault_type"],
            source_file_path,
            push=True,
        )

        incident = get_incident(incident_id)

        # Step 5: Notify
        try:
            await trigger_notify(
                incident_id,
                classification["fault_type"],
                classification["action"],
                classification["confidence"],
                classification["summary"],
                incident.get("pr_url", "pending"),
            )
        except Exception:
            pass  # Non-fatal

        update_incident(incident_id, status="completed")
        await broadcaster.broadcast("pipeline_done", {"incident_id": incident_id, "status": "completed"})

    except Exception as e:
        update_incident(incident_id, status="error", error_message=traceback.format_exc())
        await broadcaster.broadcast("pipeline_error", {"incident_id": incident_id, "error": str(e)})
        raise

    return incident_id
