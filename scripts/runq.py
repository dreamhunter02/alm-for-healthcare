#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO_ROOT / "evaluation" / "agent_queries.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "agent-runs"


def resolve_question(value: str, dataset_path: Path = DEFAULT_DATASET) -> str:
    candidate = value.strip()
    normalized = candidate.upper()
    if not (len(normalized) == 3 and normalized.startswith("Q") and normalized[1:].isdigit()):
        return candidate

    dataset = json.loads(dataset_path.read_text())
    for case in dataset["cases"]:
        if case["id"].upper() == normalized:
            return str(case["question"])
    available = ", ".join(case["id"] for case in dataset["cases"])
    raise ValueError(f"Unknown evaluation ID {candidate!r}. Available IDs: {available}")


def format_trace(record: dict[str, Any]) -> str:
    tools = record.get("tools") or []
    artifacts = record.get("artifacts") or []
    lines = ["", "=== AI-Q TOOL TRACE ==="]
    lines.extend(f"{index}. {name}" for index, name in enumerate(tools, start=1))
    if not tools:
        lines.append("(no tools recorded)")
    lines.append("=== ARTIFACTS ===")
    lines.extend(f"- {name}" for name in artifacts)
    if not artifacts:
        lines.append("(none)")
    return "\n".join(lines)


def _run_records(output_root: Path) -> set[Path]:
    return set(output_root.glob("*/run.json")) if output_root.exists() else set()


def _newest_record(output_root: Path, records_before: set[Path]) -> Path:
    records_after = _run_records(output_root)
    candidates = records_after - records_before
    if not candidates:
        candidates = records_after
    if not candidates:
        raise FileNotFoundError(f"No run.json was written under {output_root}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a healthcare ALM query, then print the authoritative AI-Q tool and artifact trace."
    )
    parser.add_argument(
        "question", nargs="+", help="An evaluation ID such as Q09, or a literal medical-device question."
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        question = resolve_question(" ".join(args.question))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"runq: {exc}")
        return 2

    records_before = _run_records(DEFAULT_OUTPUT_ROOT)
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "scripts" / "run_with_env.py"),
        str(REPO_ROOT / ".venv" / "bin" / "nat"),
        "run",
        "--config_file",
        str(REPO_ROOT / "configs" / "config_aiq_agent.yml"),
        "--input",
        question,
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    if result.returncode:
        return result.returncode

    try:
        record_path = _newest_record(DEFAULT_OUTPUT_ROOT, records_before)
        record = json.loads(record_path.read_text())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"runq: query completed, but the audit trace could not be read: {exc}")
        return 1

    print(format_trace(record))
    print(f"Run record: {record_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
