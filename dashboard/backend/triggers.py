"""
Pipeline triggers — wrappers around existing TFAH modules
that integrate with the dashboard's incident tracking and SSE.
"""

import asyncio
import json
import os
import sys
import traceback

# Ensure the project root is on sys.path so we can import agent/crash_runner/etc.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from dashboard.backend.models import (
    add_pipeline_event,
    create_incident,
    get_incident,
    update_incident,
)
from dashboard.backend.sse import broadcaster


async def _emit(incident_id: int, node: str, event_type: str, data: dict | None = None):
    payload = {"incident_id": incident_id, "node": node}
    if data:
        payload.update(data)
    add_pipeline_event(incident_id, node, event_type, data)
    await broadcaster.broadcast(f"node_{event_type}", payload)


async def trigger_crash(scenario: str | None = None) -> str:
    """Run the crash runner and return the crash log."""
    from crash_runner.run_and_capture import run_and_capture, SCENARIOS
    script = None
    if scenario and scenario in SCENARIOS:
        script = SCENARIOS[scenario][0]
    loop = asyncio.get_event_loop()
    crash_log = await loop.run_in_executor(None, run_and_capture, script)
    return crash_log


async def trigger_classify(incident_id: int, crash_log: str, source_file_path_override: str | None = None) -> dict:
    """Classify a crash log and update the incident."""
    from agent.router import classify_fault
    from notifier.slack_webhook import send_detection_alert, send_triage_complete_alert
    from automator.jira_ticket import maybe_create_incident_issue

    await _emit(incident_id, "classify", "start")
    try:
        # Send detection alert to Slack
        loop = asyncio.get_event_loop()
        source_file_path = source_file_path_override or "vulnerable_app/integration.py"
        await loop.run_in_executor(None, lambda: send_detection_alert(source_file_path=source_file_path))
        await _emit(incident_id, "classify", "slack_detection", {"notification": "detected"})

        result = await loop.run_in_executor(None, classify_fault, crash_log)

        remediation_status = (
            "Ready for remediation"
            if result["fault_type"] != "unknown"
            else "Manual review required"
        )

        # Create Jira issue
        jira_state = await loop.run_in_executor(
            None,
            lambda: maybe_create_incident_issue(
                fault_type=result["fault_type"],
                action=result["action"],
                confidence=result["confidence"],
                summary=result["summary"],
                crash_log=crash_log,
                source_file_path=source_file_path,
            ),
        )
        if jira_state.get("jira_issue_key"):
            add_pipeline_event(incident_id, "jira", "created", {
                "jira_issue_key": jira_state["jira_issue_key"],
                "jira_status": jira_state.get("jira_status", "TO DO"),
            })
            await _emit(incident_id, "classify", "jira_created", {
                "jira_issue_key": jira_state["jira_issue_key"],
                "jira_status": jira_state.get("jira_status", "TO DO"),
            })

        # Send triage complete alert to Slack
        await loop.run_in_executor(
            None,
            lambda: send_triage_complete_alert(
                fault_type=result["fault_type"],
                action=result["action"],
                confidence=result["confidence"],
                summary=result["summary"],
                remediation_status=remediation_status,
            ),
        )
        await _emit(incident_id, "classify", "slack_triage", {"notification": "triaged"})

        notifications_sent = ["detected", "triaged"]
        update_incident(
            incident_id,
            fault_type=result["fault_type"],
            http_status=result.get("http_status"),
            action=result["action"],
            confidence=result["confidence"],
            summary=result["summary"],
            pipeline_status=remediation_status,
            notifications_sent=json.dumps(notifications_sent),
            **{k: v for k, v in jira_state.items() if k.startswith("jira_")},
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
    from automator.jira_ticket import load_jira_config, maybe_transition_issue_to_status

    await _emit(incident_id, "codegen", "start")
    try:
        loop = asyncio.get_event_loop()

        # Transition Jira to IN PROGRESS
        incident = get_incident(incident_id)
        jira_key = incident.get("jira_issue_key") if incident else None
        jira_current_status = None
        if jira_key:
            jira_config = await loop.run_in_executor(None, load_jira_config)
            if jira_config:
                jira_state = await loop.run_in_executor(
                    None,
                    lambda: maybe_transition_issue_to_status(jira_key, jira_config.status_in_progress),
                )
                if jira_state.get("jira_status"):
                    update_incident(incident_id, jira_status=jira_state["jira_status"])
                    jira_current_status = jira_state["jira_status"]
                    await _emit(incident_id, "codegen", "jira_transitioned", {
                        "jira_issue_key": jira_key,
                        "jira_status": jira_state["jira_status"],
                    })

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
    from notifier.slack_webhook import send_review_ready_alert

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

        review_target = pr_url or f"local:{branch_name}"

        # Transition Jira to IN REVIEW
        incident = get_incident(incident_id)
        jira_key = incident.get("jira_issue_key") if incident else None
        jira_current_status = None
        if pr_url and jira_key:
            from automator.jira_ticket import load_jira_config, maybe_transition_issue_to_status
            jira_config = await loop.run_in_executor(None, load_jira_config)
            if jira_config:
                jira_state = await loop.run_in_executor(
                    None,
                    lambda: maybe_transition_issue_to_status(jira_key, jira_config.status_in_review),
                )
                if jira_state.get("jira_status"):
                    update_incident(incident_id, jira_status=jira_state["jira_status"])
                    jira_current_status = jira_state["jira_status"]
                    await _emit(incident_id, "open_pr", "jira_transitioned", {
                        "jira_issue_key": jira_key,
                        "jira_status": jira_state["jira_status"],
                    })

        # Send review ready alert to Slack
        await loop.run_in_executor(
            None,
            lambda: send_review_ready_alert(
                fault_type=fault_type,
                branch_name=branch_name,
                pr_url=review_target,
            ),
        )
        await _emit(incident_id, "open_pr", "slack_review_ready", {"notification": "review_ready"})

        # Update notifications_sent
        incident = get_incident(incident_id)
        prev_notifications = json.loads(incident.get("notifications_sent") or "[]") if incident else []
        notifications_sent = prev_notifications + ["review_ready"]

        pipeline_status = "PR opened" if pr_url else "Branch ready for review"
        update_incident(
            incident_id,
            branch_name=branch_name,
            pr_url=review_target,
            pipeline_status=pipeline_status,
            notifications_sent=json.dumps(notifications_sent),
        )
        await _emit(incident_id, "open_pr", "done", {"branch_name": branch_name, "pr_url": review_target})
        return {"branch_name": branch_name, "pr_url": pr_url}
    except Exception as e:
        error_detail = traceback.format_exc()
        await _emit(incident_id, "open_pr", "error", {"error": error_detail})
        update_incident(incident_id, status="error", error_message=error_detail)
        raise


async def trigger_notify(incident_id: int, fault_type: str, action: str, confidence: float, summary: str, pr_url: str, changes_summary: str = "") -> None:
    """Send Slack incident report and update the incident."""
    from notifier.slack_webhook import send_incident_report_alert

    await _emit(incident_id, "notify", "start")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: send_incident_report_alert(
                fault_type=fault_type,
                action=action,
                confidence=confidence,
                summary=summary,
                changes_summary=changes_summary,
                pr_url=pr_url,
            ),
        )

        # Transition Jira to DONE
        incident = get_incident(incident_id)
        jira_key = incident.get("jira_issue_key") if incident else None
        jira_current_status = None
        if jira_key:
            from automator.jira_ticket import load_jira_config, maybe_transition_issue_to_status
            jira_config = await loop.run_in_executor(None, load_jira_config)
            if jira_config:
                jira_state = await loop.run_in_executor(
                    None,
                    lambda: maybe_transition_issue_to_status(jira_key, jira_config.status_done),
                )
                if jira_state.get("jira_status"):
                    update_incident(incident_id, jira_status=jira_state["jira_status"])
                    jira_current_status = jira_state["jira_status"]
                    await _emit(incident_id, "notify", "jira_transitioned", {
                        "jira_issue_key": jira_key,
                        "jira_status": jira_state["jira_status"],
                    })

        # Update notifications_sent
        incident = get_incident(incident_id)
        prev_notifications = json.loads(incident.get("notifications_sent") or "[]") if incident else []
        notifications_sent = prev_notifications + ["incident_report"]

        update_incident(
            incident_id,
            notified=1,
            pipeline_status="Incident report shared",
            notifications_sent=json.dumps(notifications_sent),
        )
        await _emit(incident_id, "notify", "done", {"notified": True})
    except Exception as e:
        await _emit(incident_id, "notify", "error", {"error": str(e)})
        # Non-fatal — don't mark entire incident as error
        raise


async def run_full_pipeline(crash_log: str | None = None, scenario: str | None = None) -> int:
    """Run the complete TFAH pipeline with dashboard tracking."""
    from crash_runner.run_and_capture import SCENARIOS, DEFAULT_SCENARIO

    scenario = scenario or DEFAULT_SCENARIO
    _, source_file_path = SCENARIOS.get(scenario, SCENARIOS[DEFAULT_SCENARIO])

    # Step 1: Crash
    if not crash_log:
        crash_log = await trigger_crash(scenario=scenario)

    # Read source code
    source_path = os.path.join(PROJECT_ROOT, source_file_path)
    with open(source_path) as f:
        source_code = f.read()
    incident_id = create_incident(crash_log, source_code, source_file_path)
    await broadcaster.broadcast("pipeline_start", {"incident_id": incident_id})

    try:
        # Step 2: Classify
        classification = await trigger_classify(incident_id, crash_log, source_file_path_override=source_file_path)

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
                changes_summary=incident.get("changes_summary", ""),
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
