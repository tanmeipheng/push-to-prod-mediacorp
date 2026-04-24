#!/usr/bin/env bash
# TFAH Demo Runner
# Usage: ./demo.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Transient Fault Auto-Healer (TFAH) — Demo${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Check mock server ──
echo -e "${YELLOW}[Pre-check]${NC} Verifying mock server is running on port 8429…"
if ! curl -s http://localhost:8429/health > /dev/null 2>&1; then
    echo -e "${RED}✗ Mock server is not running.${NC}"
    echo -e "  Start it first:  ${GREEN}uv run python mock_server/server.py${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Mock server is healthy.${NC}"
echo ""

# ── Check .env ──
if [ ! -f .env ]; then
    echo -e "${RED}✗ .env file not found. Copy .env.example and fill in your keys.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ .env file found.${NC}"
echo ""

# ── Run ──
echo -e "${YELLOW}[TFAH]${NC} Launching pipeline…"
echo ""
uv run python main.py
