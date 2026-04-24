import agent.pipeline as pipeline


def test_classify_node_sends_detection_and_triage(monkeypatch):
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


def test_pr_node_sends_review_ready_update(monkeypatch):
    sent = []

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
        }
    )

    assert sent[0]["pr_url"] == "https://github.com/example/repo/pull/12"
    assert result["pipeline_status"] == "PR opened"
    assert result["notifications_sent"] == ["detected", "triaged", "review_ready"]


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
