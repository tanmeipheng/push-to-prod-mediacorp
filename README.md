# 🛡️ Transient Fault Auto-Healer (TFAH)

**An autonomous SRE agent that intercepts crash logs, classifies transient faults using an LLM, and proactively retrofits codebases with enterprise resilience patterns — delivered as a ready-to-merge Pull Request.**

Built with **LangGraph** | **Claude** | **PyGithub** | **FastAPI**

## Quick Start

```bash
uv sync                          # install all dependencies
cp .env.example .env             # fill in your keys
uv run python mock_server/server.py &   # start mock 429 server
uv run python main.py                   # run the full pipeline
```

See [agent.md](agent.md) for full repo structure and technical details.
See [demo.md](demo.md) for the demo narration script.
