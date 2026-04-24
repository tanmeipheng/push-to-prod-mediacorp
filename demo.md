# 🎬 TFAH Demo — Narration Script

> **Duration:** ~3 minutes
> **Prerequisites:** Mock server running, `.env` configured, Slack channel open, GitHub repo open

---

## Pre-Demo Setup (Before Judges Arrive)

1. **Terminal Tab 1** — Mock server running:
   ```bash
   uv run python mock_server/server.py
   ```
   Verify it's up: `curl http://localhost:8429/health` → `{"status": "ok"}`

2. **Browser Tab 1** — Slack channel open (pinned, no noise)

3. **Browser Tab 2** — GitHub repo open on `main` branch
   - Show `vulnerable_app/integration.py` — "This is our production data sync worker"

4. **Terminal Tab 2** — Ready with command typed but **NOT executed**:
   ```bash
   uv run python main.py
   ```

---

## Act 1 — "The Crash" (30 seconds)

### Narration:
> *"This is a production data-sync worker. It pulls customer records from a partner API every 15 minutes via cron. Pretty standard enterprise integration. Let's watch what happens when that partner API starts rate-limiting us."*

### Action:
Hit Enter on `python main.py` in Terminal Tab 2.

The terminal shows:
```
💥 Running vulnerable worker against mock server…

============================================================
CAPTURED CRASH LOG:
============================================================
[worker] Starting data sync from Partner API...
Traceback (most recent call last):
  File "vulnerable_app/integration.py", line 17, in sync_data
    response.raise_for_status()
  ...
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
============================================================
```

### Narration:
> *"Boom. HTTP 429 — Too Many Requests. In production, this crashes the pod, PagerDuty fires, and someone gets woken up at 3 AM. But watch what happens next…"*

---

## Act 2 — "The Agent Kicks In" (30 seconds)

### What the audience sees in the terminal:

```
🚀 Starting TFAH Agent Pipeline…

🔍 [Router] Classifying crash log…
   ➜ Fault: rate_limit_429  |  Action: exponential_backoff  |  Confidence: 0.97

🔧 [Coder] Generating resilient code + test…
   ✅ Fixed code is valid Python.
   ✅ Code generation complete.
```

### Narration:
> *"Our LangGraph agent pipeline kicked in automatically. Step one: the Router node sent the crash log to Claude and classified it as a transient HTTP 429 fault — with 97% confidence — in under 2 seconds. Step two: the Coder node generated production-grade retry logic and a mock test. No human involved."*

---

## Act 3 — "The Fix Ships Itself" (60 seconds)

### What the audience sees in the terminal:

```
📦 [Automator] Creating GitHub PR…
   Created branch: fix/transient-fault-rate_limit_429-1745432100
   PR #2 opened: https://github.com/tanmeipheng/push-to-prod-mediacorp/pull/2
   ✅ PR opened.

📢 [Notifier] Sending Slack alert…
   ✅ Slack notification sent.

============================================================
✅ TFAH Pipeline Complete!
============================================================
   Fault Type  : rate_limit_429
   Action      : exponential_backoff
   Confidence  : 0.97
   PR URL      : https://github.com/tanmeipheng/push-to-prod-mediacorp/pull/2
   Notified    : True
```

### Action:
**Switch to Browser Tab 1 (Slack).** Show the message:

```
🚨 TFAH Incident Detected
━━━━━━━━━━━━━━━━━━━━━━
Fault Type:    rate_limit_429
Action:        exponential_backoff
Confidence:    97%
Status:        🔧 Auto-remediated
━━━━━━━━━━━━━━━━━━━━━━
📎 Pull Request: https://github.com/…/pull/2
```

### Narration:
> *"The Slack channel got the triage notification instantly — fault type, confidence, remediation action, and a direct link to the PR. This is what the on-call engineer sees instead of a raw PagerDuty alert."*

### Action:
**Switch to Browser Tab 2 (GitHub).** Refresh. Open the PR. Show three things:

1. **The diff on `integration.py`:**
   > *"Look at the diff — the agent added `tenacity` with exponential backoff. Min wait 1 second, max 60, retries up to 5 times. It also added the proper import. The original function signature and docstring are preserved."*

2. **The test file `test_integration.py`:**
   > *"And here's the auto-generated test — it uses `unittest.mock.patch` to mock `requests.get`, simulates a 429 then a 200, and asserts the retry logic works. This test actually passes."*

3. **The `INCIDENT_REPORT.md`:**
   > *"And the PR description is a full incident report — root cause, remediation strategy, risk assessment, and file change summary. Audit-ready."*

---

## Act 4 — "The Big Picture" (60 seconds)

### Narration:
> *"So let's recap what just happened: a transient fault crashed our worker. Our LangGraph agent — in a four-node pipeline — classified the fault, generated the fix, shipped a PR with tests, and notified the team. Total time: under 30 seconds. Zero human intervention."*

> *"This is just 429 rate limits today. But the Router is a classification engine — 503s map to Circuit Breaker patterns, database deadlocks map to retry-with-jitter. Every resilience pattern is just a prompt template away."*

> *"In production, this plugs into your existing observability stack — Datadog, CloudWatch, PagerDuty — as a webhook consumer. The crash becomes the trigger. The PR becomes the resolution. The incident report becomes the audit trail."*

> *"We call it the Transient Fault Auto-Healer. It turns the 3 AM page into a morning PR review."*

---

## Fallback Scenarios

| If this breaks… | Do this |
|---|---|
| Claude API is slow | Say "Claude is thinking…" — it usually finishes in < 10s |
| GitHub 403 / rate limit | Show a pre-created PR from an earlier test run |
| Slack webhook fails | Show the JSON payload printed in terminal |
| Generated code has syntax error | Pipeline auto-retries once; if it fails again, show the terminal output and explain the validation step |
| Mock server isn't running | `curl: connection refused` is immediately obvious — just start it |
