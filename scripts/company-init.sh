#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"
if command -v ai-team >/dev/null 2>&1; then
  ai-team --repo-root "${REPO_ROOT}" codex-init
else
  python3 -m ai_company --repo-root "${REPO_ROOT}" codex-init
fi
