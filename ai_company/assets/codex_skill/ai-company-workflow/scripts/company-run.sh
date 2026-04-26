#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: company-run.sh '<raw user message>'" >&2
  exit 2
fi

RAW_MESSAGE="$*"
REPO_ROOT="$(pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-${HOME}/.codex}"
VENDOR_DIR="${AI_TEAM_VENDOR_DIR:-${CODEX_HOME_DIR}/vendor/ai-team}"

if command -v ai-team >/dev/null 2>&1; then
  ai-team --repo-root "${REPO_ROOT}" start-session --message "${RAW_MESSAGE}"
elif [[ -f "${VENDOR_DIR}/ai_company/cli.py" ]]; then
  PYTHONPATH="${VENDOR_DIR}${PYTHONPATH:+:${PYTHONPATH}}" python3 -m ai_company --repo-root "${REPO_ROOT}" start-session --message "${RAW_MESSAGE}"
else
  python3 -m ai_company --repo-root "${REPO_ROOT}" start-session --message "${RAW_MESSAGE}"
fi
