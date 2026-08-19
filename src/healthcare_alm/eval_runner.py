"""Live evaluation runner for the AI-Q medical-device Deep Agent."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from healthcare_alm.environment import load_workshop_environment
from healthcare_alm.evaluation import evaluate_case


def _run_records(agent_runs_dir: Path) -> set[Path]:
    return set(agent_runs_dir.glob("*/run.json"))


def _new_run_record(agent_runs_dir: Path, before: set[Path]) -> Path | None:
    candidates = _run_records(agent_runs_dir) - before
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


def run_live_evaluation(
    *,
    repo_root: Path,
    case_ids: set[str] | None = None,
    config_path: Path = Path("configs/config_aiq_agent.yml"),
    stop_on_failure: bool = False,
) -> dict[str, Any]:
    dataset = json.loads((repo_root / "evaluation/agent_queries.json").read_text())
    cases = [case for case in dataset["cases"] if case_ids is None or case["id"] in case_ids]
    if case_ids and {case["id"] for case in cases} != case_ids:
        missing = sorted(case_ids - {case["id"] for case in cases})
        raise ValueError(f"Unknown evaluation cases: {', '.join(missing)}")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir = repo_root / "output/evaluations" / timestamp
    report_dir.mkdir(parents=True, exist_ok=False)
    agent_runs_dir = repo_root / "output/agent-runs"
    agent_runs_dir.mkdir(parents=True, exist_ok=True)

    environment = load_workshop_environment(repo_root / ".env")
    environment.setdefault("AIQ_OPENSHELL_REQUIRE_HARD_LANDLOCK", "false")
    command_prefix = [
        str(repo_root / ".venv/bin/nat"),
        "run",
        "--config_file",
        str(config_path),
        "--input",
    ]

    results: list[dict[str, Any]] = []
    for case in cases:
        before = _run_records(agent_runs_dir)
        process = subprocess.run(
            [*command_prefix, case["question"]],
            cwd=repo_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        (report_dir / f"{case['id']}.log").write_text(process.stdout + process.stderr)
        record_path = _new_run_record(agent_runs_dir, before)
        if record_path is None:
            record = {
                "answer": "",
                "tools": [],
                "artifacts": [],
                "failure_reason": f"nat exited {process.returncode} without a run record",
            }
            run_dir = agent_runs_dir
            run_id = None
        else:
            record = json.loads(record_path.read_text())
            run_dir = record_path.parent
            run_id = record.get("run_id")
            if process.returncode and not record.get("failure_reason"):
                record["failure_reason"] = f"nat exited {process.returncode}"
        evaluation = evaluate_case(case, record, run_dir)
        item = {
            **evaluation.as_dict(),
            "level": case["level"],
            "category": case["category"],
            "run_id": run_id,
            "latency_seconds": record.get("latency_seconds"),
            "tools": record.get("tools", []),
            "artifacts": record.get("artifacts", []),
            "answer": record.get("answer"),
            "failure_reason": record.get("failure_reason"),
        }
        results.append(item)
        status = "PASS" if evaluation.passed else f"FAIL ({', '.join(evaluation.failures)})"
        print(f"{case['id']}: {status}", flush=True)
        if stop_on_failure and not evaluation.passed:
            break

    passed = sum(bool(item["passed"]) for item in results)
    summary = {
        "dataset": dataset["dataset"],
        "started_at": timestamp,
        "passed": passed,
        "total": len(results),
        "all_passed": passed == len(results) == len(cases),
        "results": results,
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    summary["report_dir"] = str(report_dir)
    return summary


def regrade_report(*, repo_root: Path, report_dir: Path) -> dict[str, Any]:
    """Reapply deterministic rubric checks to recorded live runs without new LLM calls."""
    dataset = json.loads((repo_root / "evaluation/agent_queries.json").read_text())
    cases = {case["id"]: case for case in dataset["cases"]}
    summary_path = report_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    for item in summary["results"]:
        run_id = item.get("run_id")
        run_dir = repo_root / "output/agent-runs" / str(run_id)
        record = json.loads((run_dir / "run.json").read_text())
        result = evaluate_case(cases[item["case_id"]], record, run_dir)
        item.update(result.as_dict())
    summary["passed"] = sum(bool(item["passed"]) for item in summary["results"])
    summary["total"] = len(summary["results"])
    summary["all_passed"] = summary["passed"] == summary["total"] == len(cases)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    summary["report_dir"] = str(report_dir)
    return summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", dest="cases", help="Run one case ID; repeat for more")
    parser.add_argument("--config", default="configs/config_aiq_agent.yml")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--regrade", type=Path, help="Regrade an existing report without new model calls")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    if args.regrade:
        summary = regrade_report(repo_root=repo_root, report_dir=args.regrade.resolve())
    else:
        summary = run_live_evaluation(
            repo_root=repo_root,
            case_ids=set(args.cases) if args.cases else None,
            config_path=Path(args.config),
            stop_on_failure=args.stop_on_failure,
        )
    print(f"Result: {summary['passed']}/{summary['total']} passed")
    print(f"Report: {summary['report_dir']}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
