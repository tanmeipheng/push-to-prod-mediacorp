import agent.pipeline as pipeline


def test_classify_node_sends_detection_triage_and_creates_jira_issue(monkeypatch):
    sent = []

    monkeypatch.setattr(
        "notifier.slack_webhook.send_detection_alert",
        lambda **kwargs: sent.append(("detected", kwargs)),
    )
    monkeypatch.setattr(
        "notifier.slack_webhook.send_triage_complete_alert",
        lambda **kwargs: sent.append(("triaged", kwargs)),
    )
    monkeypatch.setattr(
        pipeline,
        "classify_fault",
        lambda crash_log: {
            "fault_type": "rate_limit_429",
            "http_status": 429,
            "action": "exponential_backoff",
            "confidence": 0.97,
            "summary": "Transient 429 detected.",
        },
    )
    monkeypatch.setattr(
        "automator.jira_ticket.maybe_create_incident_issue",
        lambda **kwargs: {
            "jira_issue_key": "PTP-1",
            "jira_issue_url": "https://example.atlassian.net/browse/PTP-1",
            "jira_status": "TO DO",
        },
    )

    result = pipeline.classify_node(
        {
            "crash_log": "Traceback ... HTTPError: 429",
            "source_file_path": "vulnerable_app/integration.py",
        }
    )

    assert [event for event, _ in sent] == ["detected", "triaged"]
    assert sent[0][1] == {"source_file_path": "vulnerable_app/integration.py"}
    assert result["pipeline_status"] == "Ready for remediation"
    assert result["notifications_sent"] == ["detected", "triaged"]
    assert result["jira_issue_key"] == "PTP-1"
    assert result["jira_status"] == "TO DO"


def test_codegen_node_moves_jira_issue_to_in_progress(monkeypatch):
    monkeypatch.setattr(
        "automator.jira_ticket.load_jira_config",
        lambda: type("Config", (), {"status_in_progress": "IN PROGRESS"})(),
    )
    moved = []
    monkeypatch.setattr(
        "automator.jira_ticket.maybe_transition_issue_to_status",
        lambda issue_key, target_status: moved.append((issue_key, target_status)) or {"jira_status": target_status},
    )
    monkeypatch.setattr(
        pipeline,
        "generate_fix",
        lambda **kwargs: {
            "fixed_code": "print('fixed')\n",
            "test_code": "def test_ok():\n    assert True\n",
            "changes_summary": "- Added retry logic",
        },
    )

    result = pipeline.codegen_node(
        {
            "source_code": "print('broken')\n",
            "fault_type": "rate_limit_429",
            "action": "exponential_backoff",
            "summary": "Transient 429 detected.",
            "confidence": 0.97,
            "jira_issue_key": "PTP-1",
        }
    )

    assert moved == [("PTP-1", "IN PROGRESS")]
    assert result["jira_status"] == "IN PROGRESS"


def test_pr_node_sends_review_ready_update(monkeypatch):
    sent = []

    monkeypatch.setattr(
        "automator.jira_ticket.load_jira_config",
        lambda: type("Config", (), {"status_in_review": "IN REVIEW"})(),
    )
    transitions = []
    monkeypatch.setattr(
        "automator.jira_ticket.maybe_transition_issue_to_status",
        lambda issue_key, target_status: transitions.append((issue_key, target_status)) or {"jira_status": target_status},
    )
    monkeypatch.setattr(
        "automator.github_pr.create_and_push_pr",
        lambda **kwargs: ("fix/transient-fault-rate_limit_429-123", "https://github.com/example/repo/pull/12"),
    )
    monkeypatch.setattr(
        "notifier.slack_webhook.send_review_ready_alert",
        lambda **kwargs: sent.append(kwargs),
    )
    monkeypatch.setenv("TFAH_PUSH_TO_REMOTE", "true")

    result = pipeline.pr_node(
        {
            "fault_type": "rate_limit_429",
            "fixed_code": "print('fixed')",
            "test_code": "def test_ok(): pass",
            "incident_report": "# report",
            "source_file_path": "vulnerable_app/integration.py",
            "notifications_sent": ["detected", "triaged"],
            "jira_issue_key": "PTP-1",
        }
    )

    assert transitions == [("PTP-1", "IN REVIEW")]
    assert sent[0]["pr_url"] == "https://github.com/example/repo/pull/12"
    assert result["pipeline_status"] == "PR opened"
    assert result["notifications_sent"] == ["detected", "triaged", "review_ready"]
    assert result["jira_status"] == "IN REVIEW"


def test_notify_node_sends_final_incident_report(monkeypatch):
    sent = []

    monkeypatch.setattr(
        "notifier.slack_webhook.send_incident_report_alert",
        lambda **kwargs: sent.append(kwargs),
    )

    result = pipeline.notify_node(
        {
            "fault_type": "rate_limit_429",
            "action": "exponential_backoff",
            "confidence": 0.97,
            "summary": "Transient 429 detected.",
            "changes_summary": "- Added retry logic",
            "pr_url": "https://github.com/example/repo/pull/12",
            "notifications_sent": ["detected", "triaged", "review_ready"],
            "jira_issue_key": "PTP-1",
            "jira_status": "IN REVIEW",
        }
    )

    assert sent[0]["pr_url"] == "https://github.com/example/repo/pull/12"
    assert result["notified"] is True
    assert result["pipeline_status"] == "Incident report shared"
    assert result["notifications_sent"] == [
        "detected",
        "triaged",
        "review_ready",
        "incident_report",
    ]
    assert "jira_status" not in result
