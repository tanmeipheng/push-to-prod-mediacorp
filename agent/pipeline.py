"""
TFAH Agent Pipeline — LangGraph orchestration.

Graph:
  capture_crash → classify_fault → generate_fix → create_pr
                                                 → notify_slack

Each node reads/writes to a shared state TypedDict.
"""

from __future__ import annotations

import ast
import os
from typing import TypedDict

from langgraph.graph import END, StateGraph

from agent.coder import generate_fix
from agent.prompts import INCIDENT_REPORT_TEMPLATE
from agent.router import classify_fault


# ── Shared state ──────────────────────────────────────────────

class PipelineState(TypedDict, total=False):
    # inputs
    crash_log: str
    source_code: str
    source_file_path: str          # repo-relative, e.g. "vulnerable_app/integration.py"

    # after classification
    fault_type: str
    http_status: int | None
    action: str
    confidence: float
    summary: str
    pipeline_status: str
    notifications_sent: list[str]

    # after code generation
    fixed_code: str
    test_code: str
    changes_summary: str
    incident_report: str

    # after branching / PR
    branch_name: str
    pr_url: str

    # after notification
    notified: bool


# ── Node functions ────────────────────────────────────────────

def classify_node(state: PipelineState) -> dict:
    """Run the LLM router to classify the crash log."""
    from notifier.slack_webhook import (
        send_detection_alert,
        send_triage_complete_alert,
    )

    print("\n🔍 [Router] Classifying crash log…")
    send_detection_alert(
        source_file_path=state.get("source_file_path", "vulnerable_app/integration.py"),
    )
    result = classify_fault(state["crash_log"])
    print(f"   ➜ Fault: {result['fault_type']}  |  Action: {result['action']}  |  Confidence: {result['confidence']}")
    remediation_status = (
        "Ready for remediation"
        if result["fault_type"] != "unknown"
        else "Manual review required"
    )
    send_triage_complete_alert(
        fault_type=result["fault_type"],
        action=result["action"],
        confidence=result["confidence"],
        summary=result["summary"],
        remediation_status=remediation_status,
    )
    return {
        "fault_type": result["fault_type"],
        "http_status": result.get("http_status"),
        "action": result["action"],
        "confidence": result["confidence"],
        "summary": result["summary"],
        "pipeline_status": remediation_status,
        "notifications_sent": state.get("notifications_sent", []) + ["detected", "triaged"],
    }


def codegen_node(state: PipelineState) -> dict:
    """Run the LLM coder to generate fix + test."""
    print("\n🔧 [Coder] Generating resilient code + test…")
    result = generate_fix(
        source_code=state["source_code"],
        fault_type=state["fault_type"],
        action=state["action"],
        summary=state["summary"],
    )

    fixed_code = result["fixed_code"]
    test_code = result["test_code"]

    # Validate generated Python is parseable
    try:
        ast.parse(fixed_code)
        print("   ✅ Fixed code is valid Python.")
    except SyntaxError as e:
        print(f"   ⚠️  Fixed code has syntax error: {e}. Retrying…")
        result = generate_fix(
            source_code=state["source_code"],
            fault_type=state["fault_type"],
            action=state["action"],
            summary=state["summary"],
        )
        fixed_code = result["fixed_code"]
        test_code = result["test_code"]

    incident_report = INCIDENT_REPORT_TEMPLATE.format(
        fault_type=state["fault_type"],
        http_status=state.get("http_status", "N/A"),
        confidence=state["confidence"],
        action=state["action"],
        summary=state["summary"],
        changes_summary=result["changes_summary"],
    )

    print("   ✅ Code generation complete.")
    return {
        "fixed_code": fixed_code,
        "test_code": test_code,
        "changes_summary": result["changes_summary"],
        "incident_report": incident_report,
    }


def pr_node(state: PipelineState) -> dict:
    """Create a feature branch (and optionally push + open PR)."""
    print("\n📦 [Automator] Creating fix branch…")
    from automator.github_pr import create_and_push_pr
    from notifier.slack_webhook import send_review_ready_alert

    # push=True will also push to remote and open a PR
    # push=False keeps everything local (safe for dev/demo)
    should_push = os.environ.get("TFAH_PUSH_TO_REMOTE", "false").lower() == "true"

    branch_name, pr_url = create_and_push_pr(
        fixed_code=state["fixed_code"],
        test_code=state["test_code"],
        incident_report=state["incident_report"],
        fault_type=state["fault_type"],
        source_file_path=state.get("source_file_path", "vulnerable_app/integration.py"),
        push=should_push,
    )

    if pr_url:
        print(f"   ✅ PR opened: {pr_url}")
    else:
        print(f"   ✅ Branch ready (local): {branch_name}")

    review_target = pr_url or f"local:{branch_name}"
    send_review_ready_alert(
        fault_type=state["fault_type"],
        branch_name=branch_name,
        pr_url=review_target,
    )

    return {
        "branch_name": branch_name,
        "pr_url": review_target,
        "pipeline_status": "PR opened" if pr_url else "Branch ready for review",
        "notifications_sent": state.get("notifications_sent", []) + ["review_ready"],
    }


def notify_node(state: PipelineState) -> dict:
    """Send the final Slack incident report."""
    print("\n📢 [Notifier] Sending Slack incident report…")
    from notifier.slack_webhook import send_incident_report_alert

    send_incident_report_alert(
        fault_type=state["fault_type"],
        action=state["action"],
        confidence=state["confidence"],
        summary=state["summary"],
        changes_summary=state["changes_summary"],
        pr_url=state.get("pr_url", "pending"),
    )
    print("   ✅ Slack incident report sent.")
    return {
        "notified": True,
        "pipeline_status": "Incident report shared",
        "notifications_sent": state.get("notifications_sent", []) + ["incident_report"],
    }


# ── Should we act? ────────────────────────────────────────────

def should_remediate(state: PipelineState) -> str:
    """Only proceed if the fault is transient (not unknown)."""
    if state.get("fault_type", "unknown") == "unknown":
        print("   ⏭  Non-transient fault — skipping remediation.")
        return "skip"
    return "remediate"


# ── Build the graph ───────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("classify", classify_node)
    graph.add_node("codegen", codegen_node)
    graph.add_node("open_pr", pr_node)
    graph.add_node("notify", notify_node)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify",
        should_remediate,
        {"remediate": "codegen", "skip": END},
    )
    graph.add_edge("codegen", "open_pr")
    graph.add_edge("open_pr", "notify")
    graph.add_edge("notify", END)

    return graph.compile()


def run_pipeline(crash_log: str, source_code: str, source_file_path: str = "vulnerable_app/integration.py") -> PipelineState:
    """Execute the full TFAH pipeline and return the final state."""
    app = build_graph()
    initial_state: PipelineState = {
        "crash_log": crash_log,
        "source_code": source_code,
        "source_file_path": source_file_path,
    }
    final_state = app.invoke(initial_state)
    return final_state
