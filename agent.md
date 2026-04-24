# TFAH Agent Guide

## Goal
Build a one-repo demo where a vulnerable Python worker crashes on HTTP 429, TFAH classifies the fault as transient, sends a Slack alert, opens a Jira ticket, generates a retry-based fix with a mocked pytest and incident report, moves the Jira issue through the board stages, opens a GitHub PR, and posts the final incident report back to Slack with no manual code editing.

## Locked Decisions
- Stack: Python 3.11+, `uv`, `pyproject.toml`, FastAPI, `requests`, `tenacity`, `pytest`.
- Live provider: Anthropic only for v1; support `TFAH_FAKE_LLM=1` for deterministic fallback and rehearsals.
- Slack notification is a core demo step for every actionable transient incident, including the initial triage alert and the final incident report; persist equivalent local payloads for fallback and rehearsals.
- Jira ticketing is a core demo step. Use project key `PTP` and the board stages shown in the shared board: `TO DO` -> `IN PROGRESS` -> `IN REVIEW` -> `DONE`.
- PR path: real GitHub by default, local dry-run backup required.
- Git commit messages must follow Conventional Commits 1.0.0: `<type>[optional scope]: <description>`.

## Owners
- Builder A owns `tfah/` and `tests/tfah/`: router, remediator, prompts, reporting, contracts, and fixture mode.
- Builder B owns `demo_app/`, `mock_api/`, `automation/`, `demo/`, and `tests/demo/`: vulnerable worker, 429 server, crash runner, Slack notifier, Jira creator/transitioner, PR creator, and end-to-end flow.
- Presenter owns `docs/` and `artifacts/presentation/`: talk track, screenshots, sample outputs, rehearsal notes, and the Slack/Jira/GitHub demo walkthrough.
- Shared edits need a heads-up in team chat before touching repo docs, dependency config, or the contract module.

## Repo Contract
- Runtime outputs live in `artifacts/latest/` and stay untracked.
- Builder B produces `crash.log`, the target file path for remediation, `slack_event.json`, `slack_report.json`, and `jira_ticket.json`.
- Builder A produces `triage.json`, `remediation_bundle.json`, and `incident_report.md`.
- `triage.json` fields: `incident_id`, `timestamp`, `error_type`, `classification`, `pattern`, `target_file`, `should_remediate`, `confidence`, `summary`, `jira_summary`, `slack_text`.
- `jira_ticket.json` fields: `incident_id`, `jira_issue_key`, `status`, `summary`, `description`, `assignee`, `pr_url`.
- `remediation_bundle.json` fields: `incident_id`, `jira_issue_key`, `target_file`, `patched_code`, `test_path`, `test_code`, `report_md`, `branch_name`, `pr_title`, `pr_body`, `pr_url`.
- Ticket lifecycle:
  - Create Jira issue in `TO DO` as soon as the incident is classified as actionable.
  - Move the issue to `IN PROGRESS` before code generation or file edits start.
  - Move the issue to `IN REVIEW` immediately after the PR is created.
  - Move the issue to `DONE` only after the full pipeline succeeds and the final report exists.
- Standard commands:
  - `uv sync`
  - `uv run pytest`
  - `uv run python -m mock_api.app`
  - `uv run python -m demo.run_failure`
  - `uv run python -m tfah.pipeline --log artifacts/latest/crash.log --target demo_app/integration.py`
  - `uv run python -m automation.notify_slack --triage artifacts/latest/triage.json`
  - `uv run python -m automation.notify_slack --report artifacts/latest/incident_report.md --bundle artifacts/latest/remediation_bundle.json`
  - `uv run python -m automation.sync_jira --event detected --triage artifacts/latest/triage.json`
  - `uv run python -m automation.sync_jira --event review --bundle artifacts/latest/remediation_bundle.json`
  - `uv run python -m automation.open_pr --bundle artifacts/latest/remediation_bundle.json`

## External Integrations
- Required live env vars: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `GITHUB_REPO`, `SLACK_WEBHOOK_URL`, `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`.
- Set `JIRA_PROJECT_KEY=PTP` for the shared hackathon board unless the team explicitly changes projects.
- Slack triage messages must include the incident type, classification, selected action, and Jira key once created.
- The final Slack message must include the Jira key, PR URL, remediation summary, and the incident report content or a direct link to it.
- Jira issue descriptions must include the error summary, traceback excerpt, selected remediation pattern, and links to the PR and incident report once available.

## Git Workflow
- No direct commits to `develop`; use `builder-a/<task>`, `builder-b/<task>`, and `demo/integration`.
- Keep commits atomic and use Conventional Commits with lowercase types.
- Allowed common types for this repo: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- Use a scope when it adds clarity, for example:
  - `feat(router): classify 429 incidents as transient`
  - `fix(automation): handle missing GitHub token in dry-run mode`
  - `test(remediator): cover retry wrapper generation`
- Do not use vague subjects like `update stuff`, `misc fixes`, or `wip`.
- If a change is breaking, mark it with `!` or a `BREAKING CHANGE:` footer.

## Collaboration Rules
- Do not edit another owner's directory without an explicit handoff.
- If contract fields change, update both producer and consumer in the same integration pass.
- Keep the Jira transition map and Slack payload shape versioned in code, not in ad-hoc scripts.
- Post the Jira key and PR URL back into Slack so the presenter can pivot between tools during the demo.
- Treat the final incident report Slack post as a required completion step, not presenter polish.
- Post a status update every 30 minutes in chat using `done / next / blocker`.
- Secrets live only in `.env`; never hardcode or commit tokens.

## Execution Order
1. Builder B scaffolds the repo, mock API, vulnerable worker, and crash runner.
2. Builder A scaffolds the contracts and fixture-mode pipeline first.
3. Builder B implements Slack notifier and Jira create/transition client against the `PTP` workflow before polishing any UI or presenter assets.
4. Builder A implements 429 classification and retry-remediation generation.
5. Integrate on `demo/integration` with this sequence: detect incident -> send Slack alert -> create Jira in `TO DO` -> move Jira to `IN PROGRESS` -> generate fix/test/report -> open PR -> move Jira to `IN REVIEW` -> move Jira to `DONE` -> send the final incident report to Slack.
6. Add live Anthropic and GitHub behind the same interfaces; keep local payload fallbacks for Slack and Jira.
7. Spend the final hour rehearsing once live and once in fallback mode, including the Slack and Jira screens.

## Acceptance
- Actionable transient faults trigger a Slack notification with the incident summary and selected remediation action.
- A Jira issue is created in project `PTP` with a human-readable explanation of the bug and remediation plan.
- The Jira issue transitions through `TO DO`, `IN PROGRESS`, `IN REVIEW`, and `DONE` at the correct points in the pipeline.
- After the pipeline completes, Slack receives the final incident report with the Jira key and PR reference.
- Non-transient errors are ignored.
- HTTP 429 maps to exponential backoff.
- Remediator preserves the target function signature while adding retry logic.
- Generated pytest mocks repeated 429s and a later success.
- Automator creates a PR or an identical dry-run package from the remediation bundle.
- All commits in the demo branch history follow Conventional Commits.
- The demo still works if Anthropic, Slack, Jira, or GitHub is unavailable by emitting equivalent local payloads for rehearsal.
