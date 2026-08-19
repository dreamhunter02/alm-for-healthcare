import json
from types import SimpleNamespace

import pytest

from healthcare_alm.agent.deep_agent import MedicalDeviceDeepAgent


class FakeGraph:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.inputs = []

    async def ainvoke(self, value):
        self.inputs.append(value)
        if self.error:
            raise self.error
        return self.result


class FakeRuntime:
    def __init__(self):
        self.backend = object()
        self.finalized = []
        self.artifacts_finalized = []
        self.workdir = "/workspace/job-test"
        self.artifact_dir = "/workspace/job-test/aiq-artifacts"
        self.artifact_manager = None

    def finalize(self, *, interrupted):
        self.finalized.append(interrupted)
        return True

    def finalize_artifacts(self, *, interrupted):
        self.artifacts_finalized.append(interrupted)
        return True


@pytest.mark.asyncio
async def test_single_deep_agent_receives_query_without_subagents_and_finalizes():
    graph = FakeGraph(result={"messages": [{"role": "assistant", "content": "PUMP-009 is highest risk."}]})
    runtime = FakeRuntime()
    captured = {}

    def agent_factory(**kwargs):
        captured.update(kwargs)
        return graph

    runner = MedicalDeviceDeepAgent(
        model=object(),
        tools=[SimpleNamespace(name="query_hospital_database")],
        sandbox_config=object(),
        runtime_factory=lambda **_kwargs: runtime,
        agent_factory=agent_factory,
    )

    answer = await runner.run("Which pump should retire first?")

    assert answer == "PUMP-009 is highest risk."
    assert graph.inputs == [{"messages": [{"role": "user", "content": "Which pump should retire first?"}]}]
    assert captured["subagents"] == []
    assert captured["backend"] is runtime.backend
    assert "Current sandbox work directory: /workspace/job-test" in captured["system_prompt"]
    assert "Current artifact directory: /workspace/job-test/aiq-artifacts" in captured["system_prompt"]
    assert runtime.finalized == [False]
    assert runtime.artifacts_finalized == [False]


@pytest.mark.asyncio
async def test_single_deep_agent_strips_leaked_reasoning_tags_from_answer():
    graph = FakeGraph(
        result={
            "messages": [
                {
                    "role": "assistant",
                    "content": "I found the rows.</think>There are 3 ICU pumps.",
                }
            ]
        }
    )
    runner = MedicalDeviceDeepAgent(
        model=object(),
        tools=[],
        sandbox_config=object(),
        runtime_factory=lambda **_kwargs: FakeRuntime(),
        agent_factory=lambda **_kwargs: graph,
    )

    assert await runner.run("Count ICU pumps") == "There are 3 ICU pumps."


@pytest.mark.asyncio
async def test_single_deep_agent_finalizes_as_interrupted_after_failure():
    graph = FakeGraph(error=RuntimeError("model failed"))
    runtime = FakeRuntime()
    runner = MedicalDeviceDeepAgent(
        model=object(),
        tools=[],
        sandbox_config=object(),
        runtime_factory=lambda **_kwargs: runtime,
        agent_factory=lambda **_kwargs: graph,
    )

    with pytest.raises(RuntimeError, match="model failed"):
        await runner.run("run analysis")

    assert runtime.finalized == [True]
    assert runtime.artifacts_finalized == [True]


@pytest.mark.asyncio
async def test_single_deep_agent_rejects_empty_query_before_starting_runtime():
    started = False

    def runtime_factory(**_kwargs):
        nonlocal started
        started = True
        return FakeRuntime()

    runner = MedicalDeviceDeepAgent(
        model=object(),
        tools=[],
        sandbox_config=object(),
        runtime_factory=runtime_factory,
        agent_factory=lambda **_kwargs: FakeGraph(),
    )

    with pytest.raises(ValueError, match="query must not be empty"):
        await runner.run("   ")

    assert started is False


@pytest.mark.asyncio
async def test_single_deep_agent_creates_sqlite_artifact_parent_before_runtime(tmp_path):
    database_path = tmp_path / "nested" / "artifacts.db"

    def runtime_factory(**_kwargs):
        assert database_path.parent.is_dir()
        return FakeRuntime()

    runner = MedicalDeviceDeepAgent(
        model=object(),
        tools=[],
        sandbox_config=object(),
        artifact_db_url=f"sqlite:///{database_path}",
        runtime_factory=runtime_factory,
        agent_factory=lambda **_kwargs: FakeGraph(
            result={"messages": [{"role": "assistant", "content": "complete"}]}
        ),
    )

    assert await runner.run("run analysis") == "complete"


@pytest.mark.asyncio
async def test_single_deep_agent_materializes_harvested_artifacts(tmp_path):
    artifact = SimpleNamespace(artifact_id="art-1", filename="result.csv")

    class FakeStore:
        def list(self, job_id):
            assert job_id == "job-fixed"
            return [artifact]

        def open_bytes(self, job_id, artifact_id):
            assert (job_id, artifact_id) == ("job-fixed", "art-1")
            yield b"asset_id,value\nPUMP-009,74\n"

    runtime = FakeRuntime()
    runtime.artifact_manager = SimpleNamespace(store=FakeStore())
    runner = MedicalDeviceDeepAgent(
        model=object(),
        tools=[],
        sandbox_config=object(),
        artifact_output_dir=tmp_path,
        job_id_factory=lambda: "job-fixed",
        runtime_factory=lambda **_kwargs: runtime,
        agent_factory=lambda **_kwargs: FakeGraph(
            result={"messages": [{"role": "assistant", "content": "complete"}]}
        ),
    )

    assert await runner.run("run analysis") == "complete"
    assert (tmp_path / "job-fixed" / "result.csv").read_bytes() == b"asset_id,value\nPUMP-009,74\n"
    assert runner.last_artifact_paths == [tmp_path / "job-fixed" / "result.csv"]


@pytest.mark.asyncio
async def test_single_deep_agent_records_tool_trace_answer_and_latency(tmp_path):
    graph = FakeGraph(
        result={
            "messages": [
                {"role": "user", "content": "Count ICU pumps"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"name": "query_hospital_database", "args": {"sql": "SELECT 1"}}],
                },
                {"role": "tool", "name": "query_hospital_database", "content": '{"row_count": 3}'},
                {"role": "assistant", "content": "There are 3."},
            ]
        }
    )
    runner = MedicalDeviceDeepAgent(
        model=object(),
        tools=[],
        sandbox_config=object(),
        artifact_output_dir=tmp_path,
        job_id_factory=lambda: "job-trace",
        runtime_factory=lambda **_kwargs: FakeRuntime(),
        agent_factory=lambda **_kwargs: graph,
    )

    assert await runner.run("Count ICU pumps") == "There are 3."
    record = json.loads((tmp_path / "job-trace" / "run.json").read_text())
    assert record["run_id"] == "job-trace"
    assert record["question"] == "Count ICU pumps"
    assert record["answer"] == "There are 3."
    assert record["tools"] == ["query_hospital_database"]
    assert record["latency_seconds"] >= 0
    assert record["failure_reason"] is None
