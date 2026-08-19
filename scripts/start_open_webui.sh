#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [[ ! -x .venv/bin/nat ]]; then
  echo "Missing .venv. Run: python3.12 -m venv .venv && .venv/bin/python scripts/setup_aiq.py" >&2
  exit 1
fi

if ! .venv/bin/python scripts/run_with_env.py /usr/bin/true; then
  exit 1
fi

if ! command -v colima >/dev/null 2>&1; then
  echo "Colima was not found. Expected /opt/homebrew/bin/colima or a PATH entry." >&2
  exit 1
fi

if ! colima status >/dev/null 2>&1; then
  colima start
fi

mkdir -p output/open-webui
aiq_pid=""

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$aiq_pid" ]] && kill -0 "$aiq_pid" 2>/dev/null; then
    kill "$aiq_pid"
    wait "$aiq_pid" 2>/dev/null || true
  fi
  rm -f output/open-webui/aiq-server.pid
  docker compose -f compose.open-webui.yml down >/dev/null 2>&1 || true
}

if ! curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
  .venv/bin/python scripts/run_with_env.py \
    .venv/bin/nat serve \
    --config_file configs/config_aiq_agent.yml \
    --host 0.0.0.0 \
    --port 8000 \
    >output/open-webui/aiq-server.log 2>&1 &
  aiq_pid="$!"
  echo "$aiq_pid" >output/open-webui/aiq-server.pid
  trap cleanup EXIT INT TERM

  for _ in {1..60}; do
    if curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "AI-Q did not start. Read output/open-webui/aiq-server.log." >&2
  exit 1
fi

docker compose -f compose.open-webui.yml up -d

for _ in {1..90}; do
  if curl --silent --fail http://127.0.0.1:3000/ >/dev/null 2>&1; then
    echo "Healthcare ALM chat is ready: http://localhost:3000"
    open http://localhost:3000
    if [[ -n "$aiq_pid" ]]; then
      echo "Keep this terminal open. Press Ctrl-C to stop AI-Q and Open WebUI."
      wait "$aiq_pid"
    fi
    exit 0
  fi
  sleep 1
done

echo "Open WebUI did not start. Run: docker logs healthcare-alm-webui" >&2
exit 1
