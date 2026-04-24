import automator.jira_ticket as jira_ticket


def test_load_jira_config_derives_base_url_and_project_key(monkeypatch):
    monkeypatch.setenv(
        "JIRA_BOARD_URL",
        "https://example.atlassian.net/jira/software/projects/PTP/boards/1",
    )
    monkeypatch.setenv("JIRA_USER_EMAIL", "bot@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

    config = jira_ticket.load_jira_config()

    assert config is not None
    assert config.base_url == "https://example.atlassian.net"
    assert config.project_key == "PTP"
    assert config.board_id == 1


def test_transition_issue_uses_destination_status(monkeypatch):
    config = jira_ticket.JiraConfig(
        base_url="https://example.atlassian.net",
        project_key="PTP",
        user_email="bot@example.com",
        api_token="token",
    )
    monkeypatch.setattr(jira_ticket, "get_issue_status", lambda issue_key, config=None: "TO DO")

    calls = []

    def fake_request(config, method, path, *, json_body=None, params=None):
        calls.append((method, path, json_body, params))
        if method == "GET" and path.endswith("/transitions"):
            return {
                "transitions": [
                    {"id": "11", "name": "Start progress", "to": {"name": "IN PROGRESS"}},
                    {"id": "12", "name": "Review", "to": {"name": "IN REVIEW"}},
                ]
            }
        return None

    monkeypatch.setattr(jira_ticket, "_jira_request", fake_request)

    result = jira_ticket.transition_issue_to_status("PTP-1", "IN REVIEW", config=config)

    assert result["jira_status"] == "IN REVIEW"
    assert calls[-1] == (
        "POST",
        "/issue/PTP-1/transitions",
        {"transition": {"id": "12"}},
        None,
    )


def test_assign_issue_to_current_sprint_prefers_active_then_future(monkeypatch):
    config = jira_ticket.JiraConfig(
        base_url="https://example.atlassian.net",
        project_key="PTP",
        user_email="bot@example.com",
        api_token="token",
        board_url="https://example.atlassian.net/jira/software/projects/PTP/boards/2467",
        board_id=2467,
    )
    calls = []

    def fake_agile_request(config, method, path, *, json_body=None, params=None):
        calls.append((method, path, json_body, params))
        if method == "GET":
            return {
                "values": [
                    {"id": 77, "name": "PTP Sprint Active", "state": "active"},
                    {"id": 78, "name": "PTP Sprint Next", "state": "future"},
                ]
            }
        return None

    monkeypatch.setattr(jira_ticket, "_agile_request", fake_agile_request)

    result = jira_ticket.assign_issue_to_current_sprint("PTP-1", config=config)

    assert result == {
        "jira_sprint_id": "77",
        "jira_sprint_name": "PTP Sprint Active",
    }
    assert calls[-1] == (
        "POST",
        "/sprint/77/issue",
        {"issues": ["PTP-1"]},
        None,
    )


def test_assign_issue_to_current_sprint_falls_back_to_future(monkeypatch):
    config = jira_ticket.JiraConfig(
        base_url="https://example.atlassian.net",
        project_key="PTP",
        user_email="bot@example.com",
        api_token="token",
        board_url="https://example.atlassian.net/jira/software/projects/PTP/boards/2467",
        board_id=2467,
    )

    monkeypatch.setattr(
        jira_ticket,
        "_agile_request",
        lambda config, method, path, *, json_body=None, params=None: {
            "values": [{"id": 78, "name": "PTP Sprint 1", "state": "future"}]
        }
        if method == "GET"
        else None,
    )

    result = jira_ticket.assign_issue_to_current_sprint("PTP-1", config=config)

    assert result == {
        "jira_sprint_id": "78",
        "jira_sprint_name": "PTP Sprint 1",
    }
