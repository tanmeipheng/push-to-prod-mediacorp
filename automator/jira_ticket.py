"""
Jira ticket automation for TFAH incidents.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


def _truncate(text: str, limit: int = 255) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _normalize_status_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _extract_crash_excerpt(crash_log: str, max_lines: int = 4, max_chars: int = 400) -> str:
    lines = [line.strip() for line in crash_log.splitlines() if line.strip()]
    if not lines:
        return "No crash details captured."

    excerpt = " | ".join(lines[-max_lines:])
    return _truncate(excerpt, limit=max_chars)


def _parse_base_url(board_url: str) -> str:
    parsed = urlparse(board_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("JIRA_BOARD_URL must be a valid URL.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_project_key(board_url: str) -> str | None:
    patterns = [
        re.compile(r"/jira/software/(?:c/)?projects/(?P<project>[A-Za-z0-9_]+)/"),
        re.compile(r"/projects/(?P<project>[A-Za-z0-9_]+)/"),
    ]
    for pattern in patterns:
        match = pattern.search(urlparse(board_url).path + "/")
        if match:
            return match.group("project")
    return None


def _parse_board_id(board_url: str) -> int | None:
    match = re.search(r"/boards/(?P<board_id>\d+)", urlparse(board_url).path)
    if not match:
        return None
    return int(match.group("board_id"))


def _adf_paragraph(text: str) -> dict[str, Any]:
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": text}],
    }


def _jira_request(
    config: "JiraConfig",
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    url = f"{config.base_url}/rest/api/3{path}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    response = httpx.request(
        method,
        url,
        auth=(config.user_email, config.api_token),
        headers=headers,
        json=json_body,
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


def _agile_request(
    config: "JiraConfig",
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    url = f"{config.base_url}/rest/agile/1.0{path}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    response = httpx.request(
        method,
        url,
        auth=(config.user_email, config.api_token),
        headers=headers,
        json=json_body,
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    project_key: str
    user_email: str
    api_token: str
    board_url: str | None = None
    board_id: int | None = None
    issue_type: str = "Task"
    status_todo: str = "TO DO"
    status_in_progress: str = "IN PROGRESS"
    status_in_review: str = "IN REVIEW"
    status_done: str = "DONE"


def load_jira_config() -> JiraConfig | None:
    board_url = os.environ.get("JIRA_BOARD_URL", "").strip() or None
    base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    project_key = os.environ.get("JIRA_PROJECT_KEY", "").strip()
    user_email = os.environ.get("JIRA_USER_EMAIL", "").strip()
    api_token = os.environ.get("JIRA_API_TOKEN", "").strip()

    if board_url and not base_url:
        base_url = _parse_base_url(board_url)
    if board_url and not project_key:
        project_key = _parse_project_key(board_url) or ""

    missing = [
        name
        for name, value in [
            ("JIRA_BASE_URL or JIRA_BOARD_URL", base_url),
            ("JIRA_PROJECT_KEY or parseable JIRA_BOARD_URL", project_key),
            ("JIRA_USER_EMAIL", user_email),
            ("JIRA_API_TOKEN", api_token),
        ]
        if not value
    ]
    if missing:
        print(f"   ⚠️  Jira config incomplete ({', '.join(missing)}) — skipping Jira sync.")
        return None

    return JiraConfig(
        base_url=base_url.rstrip("/"),
        project_key=project_key,
        user_email=user_email,
        api_token=api_token,
        board_url=board_url,
        board_id=_parse_board_id(board_url) if board_url else None,
        issue_type=os.environ.get("JIRA_ISSUE_TYPE", "Task").strip() or "Task",
        status_todo=os.environ.get("JIRA_STATUS_TODO", "TO DO").strip() or "TO DO",
        status_in_progress=os.environ.get("JIRA_STATUS_IN_PROGRESS", "IN PROGRESS").strip() or "IN PROGRESS",
        status_in_review=os.environ.get("JIRA_STATUS_IN_REVIEW", "IN REVIEW").strip() or "IN REVIEW",
        status_done=os.environ.get("JIRA_STATUS_DONE", "DONE").strip() or "DONE",
    )


def _build_issue_summary(fault_type: str, source_file_path: str) -> str:
    return _truncate(f"TFAH Incident: {fault_type} in {source_file_path}")


def _build_issue_description(
    *,
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    crash_log: str,
    source_file_path: str,
) -> dict[str, Any]:
    excerpt = _extract_crash_excerpt(crash_log)
    return {
        "version": 1,
        "type": "doc",
        "content": [
            _adf_paragraph("Created automatically by the TFAH pipeline."),
            _adf_paragraph(f"Source file: {source_file_path}"),
            _adf_paragraph(f"Fault type: {fault_type}"),
            _adf_paragraph(f"Recommended action: {action}"),
            _adf_paragraph(f"Classification confidence: {confidence:.0%}"),
            _adf_paragraph(f"Summary: {summary}"),
            _adf_paragraph(f"Traceback excerpt: {excerpt}"),
        ],
    }


def create_incident_issue(
    *,
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    crash_log: str,
    source_file_path: str,
    config: JiraConfig | None = None,
) -> dict[str, str]:
    config = config or load_jira_config()
    if not config:
        return {}

    payload = {
        "fields": {
            "project": {"key": config.project_key},
            "summary": _build_issue_summary(fault_type, source_file_path),
            "description": _build_issue_description(
                fault_type=fault_type,
                action=action,
                confidence=confidence,
                summary=summary,
                crash_log=crash_log,
                source_file_path=source_file_path,
            ),
            "issuetype": {"name": config.issue_type},
        }
    }
    created_issue = _jira_request(config, "POST", "/issue", json_body=payload)
    issue_key = created_issue["key"]
    issue_state = {
        "jira_issue_key": issue_key,
        "jira_issue_url": f"{config.base_url}/browse/{issue_key}",
        "jira_status": config.status_todo,
    }
    issue_state.update(assign_issue_to_current_sprint(issue_key, config=config))
    return issue_state


def get_target_sprint(config: JiraConfig | None = None) -> dict[str, Any] | None:
    config = config or load_jira_config()
    if not config or not config.board_id:
        return None

    response = _agile_request(
        config,
        "GET",
        f"/board/{config.board_id}/sprint",
        params={"state": "active,future", "maxResults": 50},
    )
    sprints = response.get("values", []) if response else []
    if not sprints:
        return None

    active = next((sprint for sprint in sprints if sprint.get("state") == "active"), None)
    if active:
        return active

    return next((sprint for sprint in sprints if sprint.get("state") == "future"), None)


def assign_issue_to_current_sprint(
    issue_key: str,
    config: JiraConfig | None = None,
) -> dict[str, str]:
    config = config or load_jira_config()
    if not config or not issue_key or not config.board_id:
        return {}

    sprint = get_target_sprint(config=config)
    if not sprint:
        print("   ⚠️  No active or future sprint found on the Jira board — issue left in backlog.")
        return {}

    _agile_request(
        config,
        "POST",
        f"/sprint/{sprint['id']}/issue",
        json_body={"issues": [issue_key]},
    )
    return {
        "jira_sprint_id": str(sprint["id"]),
        "jira_sprint_name": sprint["name"],
    }


def get_issue_status(issue_key: str, config: JiraConfig | None = None) -> str:
    config = config or load_jira_config()
    if not config:
        raise RuntimeError("Jira config unavailable.")

    issue = _jira_request(
        config,
        "GET",
        f"/issue/{issue_key}",
        params={"fields": "status"},
    )
    return issue["fields"]["status"]["name"]


def transition_issue_to_status(
    issue_key: str,
    target_status: str,
    config: JiraConfig | None = None,
) -> dict[str, str]:
    config = config or load_jira_config()
    if not config or not issue_key:
        return {}

    current_status = get_issue_status(issue_key, config=config)
    if _normalize_status_name(current_status) == _normalize_status_name(target_status):
        return {
            "jira_issue_key": issue_key,
            "jira_issue_url": f"{config.base_url}/browse/{issue_key}",
            "jira_status": current_status,
        }

    transitions = _jira_request(config, "GET", f"/issue/{issue_key}/transitions")
    available = transitions.get("transitions", [])
    selected = next(
        (
            transition
            for transition in available
            if _normalize_status_name(transition.get("to", {}).get("name", "")) == _normalize_status_name(target_status)
        ),
        None,
    )
    if not selected:
        available_statuses = ", ".join(
            transition.get("to", {}).get("name", "<unknown>")
            for transition in available
        )
        raise ValueError(
            f"Jira transition to '{target_status}' is unavailable for {issue_key}. "
            f"Available destinations: {available_statuses or 'none'}."
        )

    _jira_request(
        config,
        "POST",
        f"/issue/{issue_key}/transitions",
        json_body={"transition": {"id": selected["id"]}},
    )
    return {
        "jira_issue_key": issue_key,
        "jira_issue_url": f"{config.base_url}/browse/{issue_key}",
        "jira_status": selected["to"]["name"],
    }


def maybe_create_incident_issue(**kwargs: Any) -> dict[str, str]:
    try:
        return create_incident_issue(**kwargs)
    except Exception as exc:
        print(f"   ⚠️  Jira issue creation failed: {exc}")
        return {}


def maybe_transition_issue_to_status(issue_key: str | None, target_status: str) -> dict[str, str]:
    if not issue_key:
        return {}
    try:
        return transition_issue_to_status(issue_key, target_status)
    except Exception as exc:
        print(f"   ⚠️  Jira transition failed: {exc}")
        return {}
