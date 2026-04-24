"""
Slack Webhook Notifier — Posts stage-based pipeline updates to Slack.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


def _truncate(text: str, limit: int = 900) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _format_link(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        return f"<{value}|Open Pull Request>"
    return f"`{value}`"


def _build_payload(
    *,
    fallback_text: str,
    header_text: str,
    status_text: str,
    fields: list[tuple[str, str]],
    sections: list[str],
    markdown_header: bool = False,
) -> dict[str, Any]:
    title_block: dict[str, Any]
    if markdown_header:
        title_block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": header_text},
        }
    else:
        title_block = {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text},
        }

    blocks: list[dict[str, Any]] = [
        title_block,
        {
            "type": "section",
            "fields": [{"type": "mrkdwn", "text": f"*Status:*\n{status_text}"}],
        },
    ]

    blocks[1]["fields"].extend(
        {"type": "mrkdwn", "text": f"*{label}:*\n{value}"}
        for label, value in fields
    )

    for section in sections:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": _truncate(section, limit=2800)},
            }
        )

    return {"text": fallback_text, "blocks": blocks}


def _post_payload(payload: dict[str, Any]) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        print("   ⚠️  SLACK_WEBHOOK_URL not set — skipping notification.")
        return

    resp = httpx.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()


def build_detection_payload(source_file_path: str) -> dict[str, Any]:
    return _build_payload(
        fallback_text=":rotating_light: TFAH Incident Detected",
        header_text=":rotating_light: *TFAH Incident Detected*",
        status_text=":large_yellow_circle: Detected",
        fields=[
            ("Source File", f"`{source_file_path}`"),
            ("Next Step", "`Running triage`"),
        ],
        sections=[],
        markdown_header=True,
    )


def build_triage_complete_payload(
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    remediation_status: str,
) -> dict[str, Any]:
    return _build_payload(
        fallback_text=f"TFAH triage complete: {fault_type}",
        header_text="TFAH Triage Complete",
        status_text=f":compass: {remediation_status}",
        fields=[
            ("Fault Type", f"`{fault_type}`"),
            ("Action", f"`{action}`"),
            ("Confidence", f"`{confidence:.0%}`"),
        ],
        sections=[
            f"*Triage is done.* {summary}",
        ],
    )


def build_review_ready_payload(
    fault_type: str,
    branch_name: str,
    pr_url: str,
) -> dict[str, Any]:
    pr_is_open = pr_url.startswith("http://") or pr_url.startswith("https://")
    header_text = "TFAH Pull Request Opened" if pr_is_open else "TFAH Remediation Branch Ready"
    status_text = ":package: PR opened" if pr_is_open else ":package: Branch ready"
    review_target = _format_link(pr_url)

    return _build_payload(
        fallback_text=f"TFAH review update: {fault_type}",
        header_text=header_text,
        status_text=status_text,
        fields=[
            ("Fault Type", f"`{fault_type}`"),
            ("Branch", f"`{branch_name}`"),
            ("Review Target", review_target),
        ],
        sections=["*Remediation is ready for review.*"],
    )


def build_incident_report_payload(
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    changes_summary: str,
    pr_url: str,
) -> dict[str, Any]:
    return _build_payload(
        fallback_text=f"TFAH incident report: {fault_type}",
        header_text="TFAH Incident Report",
        status_text=":white_check_mark: Incident report published",
        fields=[
            ("Fault Type", f"`{fault_type}`"),
            ("Action", f"`{action}`"),
            ("Confidence", f"`{confidence:.0%}`"),
            ("Review Target", _format_link(pr_url)),
        ],
        sections=[
            f"*Root Cause:* {summary}",
            f"*Remediation Applied:* {changes_summary}",
            "*Incident status:* `Auto-remediated and shared in Slack`",
        ],
    )


def send_detection_alert(*, source_file_path: str) -> None:
    """Post the initial error detection update to Slack."""
    _post_payload(build_detection_payload(source_file_path))


def send_triage_complete_alert(
    *,
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    remediation_status: str,
) -> None:
    """Post the triage-complete update to Slack."""
    _post_payload(
        build_triage_complete_payload(
            fault_type=fault_type,
            action=action,
            confidence=confidence,
            summary=summary,
            remediation_status=remediation_status,
        )
    )


def send_review_ready_alert(
    *,
    fault_type: str,
    branch_name: str,
    pr_url: str,
) -> None:
    """Post the PR-opened or branch-ready update to Slack."""
    _post_payload(
        build_review_ready_payload(
            fault_type=fault_type,
            branch_name=branch_name,
            pr_url=pr_url,
        )
    )


def send_incident_report_alert(
    *,
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    changes_summary: str,
    pr_url: str,
) -> None:
    """Post the final structured incident report to Slack."""
    _post_payload(
        build_incident_report_payload(
            fault_type=fault_type,
            action=action,
            confidence=confidence,
            summary=summary,
            changes_summary=changes_summary,
            pr_url=pr_url,
        )
    )


def send_triage_alert(
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    pr_url: str = "pending",
) -> None:
    """Backward-compatible alias for the triage-complete notification."""
    remediation_status = "Ready for remediation" if pr_url == "pending" else "In review"
    send_triage_complete_alert(
        fault_type=fault_type,
        action=action,
        confidence=confidence,
        summary=summary,
        remediation_status=remediation_status,
    )
