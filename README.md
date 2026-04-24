# 🛡️ Transient Fault Auto-Healer (TFAH)

**An autonomous SRE agent that intercepts crash logs, classifies transient faults using an LLM, and proactively retrofits codebases with enterprise resilience patterns — delivered as a ready-to-merge Pull Request.**

Hackathon workspace for the Transient Fault Auto-Healer (TFAH) demo, including Slack triage alerts and final incident reporting, Jira ticket orchestration, and GitHub PR automation.

Built with **LangGraph** | **Claude** | **PyGithub** | **FastAPI**

## Quick Start

```bash
uv sync                          # install all dependencies
cp .env.example .env             # fill in your keys
uv run python mock_server/server.py &   # start mock 429 server
uv run python main.py                   # run the full pipeline
```

See [agent.md](agent.md) for full repo structure, technical details, and original project goals.
See [demo.md](demo.md) for the demo narration script.
