# TFAH Agent Guide

## Goal
Build a one-repo demo where a vulnerable Python worker crashes on HTTP 429, TFAH classifies the fault as transient, generates a retry-based fix with a mocked pytest and incident report, and opens a GitHub PR with no manual code editing.

## Locked Decisions
- Stack: Python 3.11+, `uv`, `pyproject.toml`, FastAPI, `requests`, `tenacity`, `pytest`.
- Live provider: Anthropic only for v1; support `TFAH_FAKE_LLM=1` for deterministic fallback and rehearsals.
- PR path: real GitHub by default, local dry-run backup required.
- Slack notifier is optional polish and gets dropped before any core pipeline work.
- Git commit messages must follow Conventional Commits 1.0.0: `<type>[optional scope]: <description>`.

## Owners
- Builder A owns `tfah/` and `tests/tfah/`: router, remediator, prompts, reporting, contracts, and fixture mode.
- Builder B owns `demo_app/`, `mock_api/`, `automation/`, `demo/`, and `tests/demo/`: vulnerable worker, 429 server, crash runner, PR creator, notifier, and end-to-end flow.
- Presenter owns `docs/` and `artifacts/presentation/`: talk track, screenshots, sample outputs, and rehearsal notes.
- Shared edits need a heads-up in team chat before touching repo docs, dependency config, or the contract module.

## Repo Contract
- Runtime outputs live in `artifacts/latest/` and stay untracked.
- Builder B produces `crash.log` and the target file path for remediation.
- Builder A produces `triage.json`, `remediation_bundle.json`, and `incident_report.md`.
- `triage.json` fields: `incident_id`, `timestamp`, `error_type`, `classification`, `pattern`, `target_file`, `should_remediate`, `confidence`, `summary`.
- `remediation_bundle.json` fields: `incident_id`, `target_file`, `patched_code`, `test_path`, `test_code`, `report_md`, `branch_name`, `pr_title`, `pr_body`.
- Standard commands:
  - `uv sync`
  - `uv run pytest`
  - `uv run python -m mock_api.app`
  - `uv run python -m demo.run_failure`
  - `uv run python -m tfah.pipeline --log artifacts/latest/crash.log --target demo_app/integration.py`
  - `uv run python -m automation.open_pr --bundle artifacts/latest/remediation_bundle.json`

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
- Post a status update every 30 minutes in chat using `done / next / blocker`.
- Secrets live only in `.env`; never hardcode or commit tokens.

## Execution Order
1. Builder B scaffolds the repo, mock API, vulnerable worker, and crash runner.
2. Builder A scaffolds the contracts and fixture-mode pipeline first.
3. Builder A implements 429 classification and retry-remediation generation.
4. Builder B implements PR dry-run, then live GitHub PR creation.
5. Integrate on `demo/integration`; add Anthropic live mode behind the same interface.
6. Add Slack only if the PR flow already works.
7. Spend the final hour rehearsing once live and once in fallback mode.

## Acceptance
- Non-transient errors are ignored.
- HTTP 429 maps to exponential backoff.
- Remediator preserves the target function signature while adding retry logic.
- Generated pytest mocks repeated 429s and a later success.
- Automator creates a PR or an identical dry-run package from the remediation bundle.
- All commits in the demo branch history follow Conventional Commits.
- The demo still works if Anthropic or GitHub is unavailable.
