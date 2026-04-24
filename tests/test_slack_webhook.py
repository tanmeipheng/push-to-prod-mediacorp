from notifier.slack_webhook import (
    build_detection_payload,
    build_incident_report_payload,
    build_review_ready_payload,
    build_triage_complete_payload,
)


def _block_texts(payload: dict) -> list[str]:
    texts = [payload["text"]]
    for block in payload["blocks"]:
        if "text" in block:
            text = block["text"]
            if isinstance(text, dict):
                texts.append(text["text"])
        for field in block.get("fields", []):
            texts.append(field["text"])
    return texts


def test_detection_payload_mentions_triage_and_excerpt():
    payload = build_detection_payload("vulnerable_app/integration.py")

    texts = _block_texts(payload)

    assert payload["text"] == ":rotating_light: TFAH Incident Detected"
    assert any("TFAH Incident Detected" in text for text in texts)
    assert any("Running triage" in text for text in texts)
    assert not any("Error excerpt" in text for text in texts)


def test_triage_payload_explicitly_says_triage_is_done():
    payload = build_triage_complete_payload(
        fault_type="rate_limit_429",
        action="exponential_backoff",
        confidence=0.97,
        summary="The upstream API returned HTTP 429 without retry handling.",
        remediation_status="Ready for remediation",
    )

    texts = _block_texts(payload)

    assert any("Triage Complete" in text for text in texts)
    assert any("Triage is done." in text for text in texts)
    assert any("Ready for remediation" in text for text in texts)


def test_review_ready_payload_includes_pr_link():
    payload = build_review_ready_payload(
        fault_type="rate_limit_429",
        branch_name="fix/transient-fault-rate_limit_429-123",
        pr_url="https://github.com/example/repo/pull/12",
    )

    texts = _block_texts(payload)

    assert any("Pull Request Opened" in text for text in texts)
    assert any("Open Pull Request" in text for text in texts)
    assert not any("Changes:" in text for text in texts)


def test_incident_report_payload_contains_structured_report_sections():
    payload = build_incident_report_payload(
        fault_type="rate_limit_429",
        action="exponential_backoff",
        confidence=0.97,
        summary="The worker crashed on a transient 429 from the upstream API.",
        changes_summary="- Added retry with exponential backoff",
        pr_url="https://github.com/example/repo/pull/12",
    )

    texts = _block_texts(payload)

    assert any("Incident Report" in text for text in texts)
    assert any("Root Cause" in text for text in texts)
    assert any("Remediation Applied" in text for text in texts)
