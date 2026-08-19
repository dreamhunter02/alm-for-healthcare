from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

SYSTEM_PROMPT = """You are a medical-device asset lifecycle management analyst for a workshop demo.

Answer the user's actual question by selecting only the tools needed to produce an evidence-backed result.

Rules:
1. Call describe_hospital_database before writing SQL. query_hospital_database accepts only read-only SELECT/WITH SQL.
2. For calculations or plots explicitly requested with code, retrieve the required rows and use the OpenShell tools.
   Always call write_file to save the generated Python script, then call execute to run that script. Do not embed the
   program inline in an execute command. Put final CSV, PNG, JSON, Markdown, or notebook artifacts in the artifact
   directory below.
   For fleet downtime analysis, use inventory.days_out_of_service: it is the authoritative cumulative per-asset total.
   maintenance_events contains only illustrative work-order samples and must not be summed as total fleet downtime.
3. Use score_retirement_risk and build_replacement_plan for retirement decisions. Never invent or alter the formula.
   For every budget or replacement-plan question, call score_retirement_risk first and build_replacement_plan second.
4. MAUDE and recall data are public model/product-level safety signals. Never attribute a report or recall to a specific
   hospital unit, claim causality, or calculate incidence/failure rates without a valid exposure denominator.
   Always use search_maude_events for MAUDE evidence and the search_device_recalls MCP tool for recall evidence.
   Never query MAUDE or recall records through query_hospital_database.
   Every answer using FDA evidence must explicitly say it is model/product-level evidence, does not establish unit
   causality, and requires human clinical-engineering review.
5. Hospital inventory and maintenance data are fictional. State that explicitly in every answer using hospital records.
   Every retirement, replacement, maintenance, or procurement recommendation requires human clinical-engineering review.
6. Cite the FDA source URLs returned by tools. End with a concise answer and list any generated artifact filenames.
7. Report computed percentages with at least two decimal places and include the numerator and denominator.
8. End every answer based on hospital records with the exact label: "Fictional hospital workshop data."
9. When asked which hospital assets match a condition, preserve row-level results and list every exact asset_id.
   Never replace asset IDs with a manufacturer/model count.
"""


def _default_runtime_factory(**kwargs):
    from aiq_agent.agents.deep_researcher.deepagents_runtime import DeepAgentsRuntime

    return DeepAgentsRuntime(**kwargs)


def _default_agent_factory(**kwargs):
    from deepagents import create_deep_agent

    return create_deep_agent(**kwargs)


def _default_job_id() -> str:
    return str(uuid4())


def _message_text(message: Any) -> str:
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        pieces = []
        for block in content:
            if isinstance(block, str):
                pieces.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                pieces.append(block["text"])
        return "\n".join(pieces).strip()
    return str(content or "").strip()


def _final_answer_text(message: Any) -> str:
    """Extract user-facing text while removing Nemotron reasoning-tag leakage."""
    text = _message_text(message)
    if "</think>" in text:
        text = text.rsplit("</think>", maxsplit=1)[-1]
    return text.replace("<think>", "").strip()


def _tool_names(messages: Sequence[Any]) -> list[str]:
    names: list[str] = []
    for message in messages:
        calls = message.get("tool_calls", []) if isinstance(message, dict) else getattr(message, "tool_calls", [])
        for call in calls or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if isinstance(name, str) and name not in names:
                names.append(name)
        role = message.get("role") if isinstance(message, dict) else getattr(message, "type", None)
        name = message.get("name") if isinstance(message, dict) else getattr(message, "name", None)
        if role == "tool" and isinstance(name, str) and name not in names:
            names.append(name)
    return names


class MedicalDeviceDeepAgent:
    """One Deep Agent with healthcare tools and an AI-Q-owned sandbox runtime."""

    def __init__(
        self,
        *,
        model: Any,
        tools: Sequence[Any],
        sandbox_config: Any,
        artifact_db_url: str | None = None,
        artifact_output_dir: Path | str = Path("output/agent-runs"),
        job_id_factory: Callable[[], str] = _default_job_id,
        runtime_factory: Callable[..., Any] = _default_runtime_factory,
        agent_factory: Callable[..., Any] = _default_agent_factory,
    ) -> None:
        self.model = model
        self.tools = list(tools)
        self.sandbox_config = sandbox_config
        self.artifact_db_url = artifact_db_url
        self.artifact_output_dir = Path(artifact_output_dir)
        self.job_id_factory = job_id_factory
        self.runtime_factory = runtime_factory
        self.agent_factory = agent_factory
        self.last_artifact_events: list[dict[str, Any]] = []
        self.last_artifact_paths: list[Path] = []
        self.last_run_id: str | None = None

    def _materialize_artifacts(self, runtime: Any, job_id: str) -> None:
        manager = getattr(runtime, "artifact_manager", None)
        if manager is None:
            return
        store = manager.store
        artifacts = store.list(job_id)
        if not artifacts:
            return
        run_dir = self.artifact_output_dir / job_id
        run_dir.mkdir(parents=True, exist_ok=True)
        for artifact in artifacts:
            filename = Path(artifact.filename).name
            destination = run_dir / filename
            destination.write_bytes(b"".join(store.open_bytes(job_id, artifact.artifact_id)))
            self.last_artifact_paths.append(destination)

    def _write_run_record(
        self,
        *,
        job_id: str,
        query: str,
        answer: str | None,
        messages: Sequence[Any],
        started_at: float,
        failure_reason: str | None,
    ) -> None:
        run_dir = self.artifact_output_dir / job_id
        run_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "run_id": job_id,
            "question": query,
            "answer": answer,
            "tools": _tool_names(messages),
            "latency_seconds": round(time.monotonic() - started_at, 3),
            "artifacts": [path.name for path in self.last_artifact_paths],
            "artifact_events": self.last_artifact_events,
            "failure_reason": failure_reason,
        }
        (run_dir / "run.json").write_text(json.dumps(record, indent=2, default=str) + "\n")

    async def run(self, query: str) -> str:
        if not query.strip():
            raise ValueError("query must not be empty")
        if self.artifact_db_url and self.artifact_db_url.startswith("sqlite:///"):
            Path(self.artifact_db_url.removeprefix("sqlite:///")).expanduser().parent.mkdir(
                parents=True, exist_ok=True
            )
        self.last_artifact_events = []
        self.last_artifact_paths = []
        job_id = self.job_id_factory()
        self.last_run_id = job_id
        started_at = time.monotonic()
        answer: str | None = None
        messages: list[Any] = []
        failure_reason: str | None = None
        main_error: BaseException | None = None
        runtime = self.runtime_factory(
            sandbox=self.sandbox_config,
            job_id=job_id,
            artifact_db_url=self.artifact_db_url,
            artifact_emit=self.last_artifact_events.append,
        )
        interrupted = True
        try:
            runtime_prompt = (
                f"{SYSTEM_PROMPT}\n"
                f"Current sandbox work directory: {runtime.workdir}\n"
                f"Current artifact directory: {runtime.artifact_dir}\n"
                "Use these exact job-scoped paths; do not use a generic /workspace/aiq-artifacts path."
            )
            graph = self.agent_factory(
                model=self.model,
                tools=self.tools,
                system_prompt=runtime_prompt,
                subagents=[],
                backend=runtime.backend,
                name="medical_device_alm_agent",
            )
            result = await graph.ainvoke({"messages": [{"role": "user", "content": query}]})
            messages = result.get("messages", []) if isinstance(result, dict) else getattr(result, "messages", [])
            if not messages:
                raise RuntimeError("Deep Agent returned no messages")
            answer = _final_answer_text(messages[-1])
            if not answer:
                raise RuntimeError("Deep Agent returned an empty final answer")
            interrupted = False
            return answer
        except BaseException as exc:
            main_error = exc
            failure_reason = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            artifact_error: BaseException | None = None
            try:
                runtime.finalize_artifacts(interrupted=interrupted)
                self._materialize_artifacts(runtime, job_id)
            except BaseException as exc:
                artifact_error = exc
                failure_reason = failure_reason or f"{type(exc).__name__}: {exc}"
            finally:
                runtime.finalize(interrupted=interrupted)
                self._write_run_record(
                    job_id=job_id,
                    query=query,
                    answer=answer,
                    messages=messages,
                    started_at=started_at,
                    failure_reason=failure_reason,
                )
            if artifact_error is not None and main_error is None:
                raise artifact_error
