#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

docker compose -f compose.open-webui.yml down

pid_file="output/open-webui/aiq-server.pid"
if [[ -f "$pid_file" ]]; then
  pid="$(<"$pid_file")"
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if [[ "$command_line" == *"nat serve"*"configs/config_aiq_agent.yml"* ]]; then
    kill "$pid"
  fi
  rm -f "$pid_file"
fi

echo "Healthcare ALM chat stopped. Colima remains available for OpenShell."
