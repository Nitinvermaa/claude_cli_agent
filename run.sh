#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
CLI_FILE="${SCRIPT_DIR}/claude_agent_cli.py"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Error: ${PYTHON_BIN} is not installed or not on PATH." >&2
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo "Warning: ${ROOT_DIR}/.env not found. Create it from .env.example first." >&2
fi

exec "${PYTHON_BIN}" "${CLI_FILE}" "$@"
