<h1 align="center">🛡️ Transient Fault Auto-Healer (TFAH)</h1>

<p align="center">
  <strong>An autonomous SRE agent that intercepts crash logs, classifies transient faults using an LLM, and proactively retrofits codebases with enterprise resilience patterns — delivered as a ready-to-merge Pull Request.</strong>
</p>

<p align="center">
  <a href="#demo-video">Demo Video</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#dashboard">Dashboard</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#tech-stack">Tech Stack</a>
</p>

---

## The Problem

Production services crash from **transient faults** — HTTP 429s, 503s, 504s, connection timeouts, database deadlocks. The industry response is reactive: PagerDuty fires, an engineer gets woken up at 3 AM, spends 30 minutes writing retry logic, opens a PR, waits for review. Rinse and repeat.

**TFAH turns the 3 AM page into a morning PR review.**

---

## Demo Video

https://github.com/user-attachments/assets/YOUR_VIDEO_ID](https://youtu.be/hIc4GulS94o

> 📹 **[Watch the full demo →](https://youtu.be/hIc4GulS94o)**
>
> *Upload the video to a GitHub release or drag it into a GitHub issue to get a streamable link, then replace the placeholder above.*

---

## How It Works

```
  Crash Detected         LLM Classifies          LLM Generates Fix         Ships It
 ┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐     ┌────────────────────┐
 │ Worker hits  │────▶│ Router Agent     │────▶│ Coder Agent       │────▶│ GitHub PR opened   │
 │ transient    │     │ fault_type: 429  │     │ + tenacity retry  │     │ Jira ticket moved  │
 │ fault        │     │ action: backoff  │     │ + pytest tests    │     │ Slack team notified│
 │              │     │ confidence: 97%  │     │ + incident report │     │                    │
 └──────────────┘     └──────────────────┘     └───────────────────┘     └────────────────────┘
                                                                              ⏱️ < 30 seconds
```

### End-to-End Pipeline

1. **Crash Capture** — A vulnerable worker hits a transient fault (429/503/504/timeout/deadlock). The crash runner captures the full stack trace.
2. **Fault Classification** — The Router agent (Claude) analyzes the crash log and returns a structured classification: fault type, remediation action, confidence score, and summary.
3. **Code Generation** — The Coder agent (Claude) reads the original source, generates production-grade resilient code using `tenacity` retry patterns, writes a matching pytest test, and produces an incident report.
4. **PR Automation** — Creates a feature branch with 3 atomic commits (fix, test, incident report), pushes to GitHub, and opens a PR with the full incident report as the body.
5. **Jira Orchestration** — Automatically creates a Jira incident ticket, assigns it to the active sprint, and transitions it through workflow stages (TO DO → IN PROGRESS → IN REVIEW → DONE) as the pipeline progresses.
6. **Slack Notifications** — Sends 4 stage-based alerts: Detection, Triage Complete, Review Ready (tags code owner), and Final Incident Report.

### Supported Failure Scenarios

| Scenario | Fault Type | Resilience Pattern Injected | Vulnerable Worker |
|----------|-----------|----------------------------|-------------------|
| `429` | Rate Limit | Exponential backoff with max retries | Data Sync Worker |
| `503` | Service Unavailable | Circuit breaker with fallback | Inventory Sync Worker |
| `504` | Gateway Timeout | Retry with timeout escalation | Payment Gateway Worker |
| `timeout` | Connection Timeout | Connection pool reset + deadline | Metrics Collector |
| `deadlock` | Database Deadlock | Retry with jitter + lock ordering | Report Generator |

---

## Architecture

### LangGraph Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐     ┌──────────┐
│   classify   │────▶│   codegen    │────▶│  open_pr  │────▶│  notify  │──▶ END
│  (Router)    │     │  (Coder)     │     │ (GitHub)  │     │ (Slack)  │
└─────────────┘     └──────────────┘     └───────────┘     └──────────┘
       │
       │ fault_type == "unknown"
       ▼
    SKIP → END
```

Built as a **LangGraph `StateGraph`** with typed state and conditional routing — unknown faults are gracefully skipped.

### System Architecture

```
                         ┌─────────────────────────────────┐
                         │       Next.js Dashboard         │
                         │   (Real-time Command Center)    │
                         │  ┌───────────┬────────────────┐ │
                         │  │ Pipeline  │  Incident      │ │
                         │  │ Visualizer│  Detail Drawer  │ │
                         │  │ (ReactFlow│  (Diff, Logs,  │ │
                         │  │  + SSE)   │   Timeline)    │ │
                         │  └───────────┴────────────────┘ │
                         └──────────────┬──────────────────┘
                                        │ REST + SSE
                         ┌──────────────▼──────────────────┐
                         │     FastAPI Backend              │
                         │  ┌────────┬────────┬──────────┐ │
                         │  │ Trigger│  SSE   │ Incident │ │
                         │  │ Engine │Broadcast│  Store   │ │
                         │  └───┬────┴────────┴──────────┘ │
                         └──────┼───────────────────────────┘
                    ┌───────────┼───────────────────────┐
                    ▼           ▼           ▼           ▼
              ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────┐
              │ LangGraph│ │ GitHub │ │  Slack   │ │  Jira  │
              │ Pipeline │ │  API   │ │ Webhooks │ │ Cloud  │
              │(Claude)  │ │(PyGithub│ │ (httpx)  │ │(REST)  │
              └──────────┘ └────────┘ └──────────┘ └────────┘
```

### Project Structure

```
push-to-prod-mediacorp/
├── main.py                          # CLI entry point — full pipeline
├── Procfile                         # Render.com deployment
├── render.yaml                      # Render blueprint
│
├── agent/                           # 🧠 LLM-powered pipeline
│   ├── router.py                    #    Crash log → fault classification (Claude)
│   ├── coder.py                     #    Source + fault → resilient code + tests (Claude)
│   ├── pipeline.py                  #    LangGraph StateGraph orchestration
│   └── prompts.py                   #    All LLM prompt templates
│
├── automator/                       # 🤖 Automation integrations
│   ├── github_pr.py                 #    Branch, commit, push, open PR (PyGithub)
│   └── jira_ticket.py               #    Create ticket, assign sprint, transition status
│
├── notifier/
│   └── slack_webhook.py             # 📢 4-stage Slack Block Kit notifications
│
├── crash_runner/
│   └── run_and_capture.py           # 💥 Subprocess crash capture + scenario registry
│
├── vulnerable_app/                  # 🎯 5 failure scenario workers (no resilience)
│   ├── integration.py               #    429 Rate Limit
│   ├── service_down.py              #    503 Service Unavailable
│   ├── gateway_timeout.py           #    504 Gateway Timeout
│   ├── connection_timeout.py        #    Connection Timeout
│   └── db_deadlock.py               #    Database Deadlock
│
├── dashboard/
│   ├── backend/                     # ⚡ FastAPI + SQLite + SSE
│   │   ├── app.py                   #    REST + SSE endpoints
│   │   ├── models.py                #    Incident & event storage
│   │   ├── triggers.py              #    Pipeline step orchestration
│   │   └── sse.py                   #    Fan-out SSE broadcaster
│   └── frontend/                    # 🖥️ Next.js 16 + React 19 + Tailwind
│       └── src/
│           ├── app/page.tsx         #    Command Center dashboard
│           ├── app/incidents/       #    Incident history + filters
│           ├── components/          #    PipelineGraph, CodeDiff, TriggerPanel, etc.
│           └── lib/                 #    API client + SSE hooks
│
├── mock_server/
│   └── server.py                    # 🎭 FastAPI mock returning 429/503/504/timeout
│
└── tests/                           # ✅ Pipeline + integration tests
```

---

## Dashboard

The **TFAH Command Center** is a real-time dashboard for monitoring and triggering the auto-healing pipeline.

### Features

- **Pipeline Visualizer** — Interactive node graph (ReactFlow) showing real-time pipeline execution status via SSE
- **Scenario Trigger Panel** — One-click buttons to run any of the 5 failure scenarios through the full pipeline
- **Incident Cards** — Live-updating list with fault type, confidence score, Jira ticket badge, PR link, and status
- **Incident Detail Drawer** — Slide-in panel with crash log viewer, side-by-side code diff (original → fixed), generated test code, pipeline event timeline, and action buttons (Replay, Open PR, Notify)
- **Stats Bar** — Total incidents, auto-fixed count, Jira tickets created, PRs opened
- **Timeline Chart** — 7-day area chart of incident volume (Recharts)
- **Filter & Search** — Filter incidents by status (completed/error/skipped/running) and fault type

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Anthropic API key](https://console.anthropic.com/) (Claude)
- GitHub Personal Access Token (with `repo` scope)

### Setup

```bash
# 1. Clone & install
git clone https://github.com/tanmeipheng/push-to-prod-mediacorp.git
cd push-to-prod-mediacorp
uv sync                               # or: pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys (ANTHROPIC_API_KEY, GITHUB_TOKEN, etc.)

# 3. Start the mock server (simulates faulty APIs)
uv run python mock_server/server.py &

# 4a. Run via CLI (single pipeline run)
uv run python main.py                  # default 429 scenario
uv run python main.py --scenario 503   # specific scenario

# 4b. Run via Dashboard (recommended)
# Terminal 1: Backend
uv run uvicorn dashboard.backend.app:app --reload --port 8000

# Terminal 2: Frontend
cd dashboard/frontend && npm install && npm run dev

# Open http://localhost:3000
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Agentic Framework** | LangGraph | StateGraph pipeline with conditional routing |
| **LLM** | Claude (Anthropic) | Crash classification + code generation |
| **Backend** | FastAPI + Uvicorn | REST API + SSE broadcasting |
| **Frontend** | Next.js 16 + React 19 | Real-time dashboard |
| **Styling** | Tailwind CSS 4 | UI components |
| **Visualization** | ReactFlow + Recharts | Pipeline graph + timeline charts |
| **Animation** | Framer Motion | Smooth UI transitions |
| **Database** | SQLite (WAL mode) | Incident + event storage |
| **GitHub** | PyGithub | Branch, commit, PR automation |
| **Jira** | Jira Cloud REST API | Ticket lifecycle management |
| **Notifications** | Slack Incoming Webhooks | 4-stage Block Kit alerts |
| **HTTP Client** | httpx | Async HTTP for Slack + Jira |
| **Retry Library** | tenacity | Injected resilience pattern |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API key for Claude |
| `GITHUB_TOKEN` | ✅ | GitHub PAT with `repo` scope |
| `GITHUB_REPO` | ✅ | Target repo (`owner/name` format) |
| `SLACK_WEBHOOK_URL` | Optional | Slack Incoming Webhook URL |
| `SLACK_CODE_OWNER` | Optional | Slack member ID for PR review mentions |
| `MOCK_SERVER_URL` | Optional | Mock server URL (default: `http://localhost:8429`) |
| `JIRA_BOARD_URL` | Optional | Jira board URL (auto-derives project key + board ID) |
| `JIRA_USER_EMAIL` | Optional | Jira Cloud email for auth |
| `JIRA_API_TOKEN` | Optional | Jira Cloud API token |
| `TFAH_PUSH_TO_REMOTE` | Optional | Set `true` to push branches + open PRs |
| `TFAH_BASE_BRANCH` | Optional | Base branch for PRs (default: `main`) |

See [.env.example](.env.example) for the full template.

---

## Deployment

| Service | Platform | Tier |
|---------|----------|------|
| Backend API | [Render.com](https://render.com) | Free |
| Frontend | [Vercel](https://vercel.com) | Free |

Deployment configs included: [`Procfile`](Procfile), [`render.yaml`](render.yaml), and [`next.config.ts`](dashboard/frontend/next.config.ts) with environment-driven API URLs.

---

## Team

**Push to Prod** — Built for the hackathon with ❤️ and too much coffee.

---

<p align="center">
  <em>"It turns the 3 AM page into a morning PR review."</em>
</p>
