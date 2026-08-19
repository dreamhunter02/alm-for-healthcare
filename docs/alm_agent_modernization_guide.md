# Modernizing an Asset Lifecycle Management Agent

## Recommended target

Move from a fixed, multi-agent showcase to a query-driven agent with explicit trust boundaries:

```text
User query
    |
Deep agent
    +-- schema inspection + read-only SQL
    +-- domain evidence adapters
    +-- deterministic scoring and planning
    +-- sandboxed code execution
    +-- artifact and trace registry
    |
Evidence-backed answer + reproducible artifacts
```

The language model should decide which capability to invoke and how to explain the result. It should not become the database, the decision policy, the execution boundary, or the source of record.

## 1. Replace specialist agents with composable capabilities

Start with one capable agent. Preserve domain functionality as typed tools and add subagents only after evaluations demonstrate a need for parallelism, context isolation, or independent review.

| Existing concept | Modern capability | Boundary |
|---|---|---|
| SQL agent | `describe_asset_database` + `query_asset_database` | Read-only data access |
| Plotting/code agent | Sandbox file and execution tools | Untrusted generated code |
| Anomaly agent | Optional validated anomaly service | Versioned domain model |
| RUL agent | Optional validated prediction service | Versioned domain model |
| Planner/router | One deep-agent control loop | Dynamic tool selection |
| Shared output directory | Per-run artifact workspace + manifest | Explicit handoffs |
| Prompt-only scoring | Deterministic scoring tool | Governed policy |

This preserves the useful pieces of the original design while removing coordination overhead and implicit file coupling.

## 2. Make the user query the primary interface

The default path should accept a real user question, not trigger a fixed pipeline or dashboard route. The agent should inspect available capabilities, choose the smallest useful trajectory, verify the result, and respond.

A useful control loop is:

1. **Inspect** — understand schemas and tool contracts.
2. **Plan** — choose the minimum evidence path.
3. **Act** — call SQL, evidence, scoring, planning, or sandbox tools.
4. **Verify** — check rows, confidence, calculations, and artifacts.
5. **Respond** — separate facts, inferences, caveats, and recommendations.

Not every query should call every tool. A fleet count may require schema inspection and SQL only. A replacement plan may require SQL, external evidence, deterministic scoring, and planning. A calculated analysis or visualization should additionally require sandbox execution.

## 3. Treat tools as contracts, not prompt suggestions

Every tool needs a narrow purpose, structured inputs, structured outputs, and an invariant that the model cannot bypass.

Recommended minimum capability set:

| Capability | Input | Output | Required invariant |
|---|---|---|---|
| Describe database | None | Tables, columns, meanings | Must precede generated SQL |
| Query database | `SELECT` or `WITH` | Rows + row count + provenance | Read-only; bounded result set |
| Search event evidence | Asset/product identifiers | Normalized records + source URLs | Preserve evidence granularity |
| Search regulatory evidence | Asset/product identifiers | Status + dates + source URLs | Separate retrieval boundary |
| Score lifecycle risk | Asset IDs or structured evidence | Components + total + action | Deterministic versioned formula |
| Build replacement plan | Candidate IDs + budget | Current/deferred phases + totals | Never rewrite risk scores |

Return recoverable tool errors. A schema error should help the agent revise the query; it should not crash the entire run or silently return an empty result.

## 4. Constrain SQL autonomy

Natural-language SQL is useful only when the data boundary is strict.

- Require schema inspection before query generation.
- Permit only a single `SELECT` or `WITH` statement.
- Reject mutations, DDL, pragmas, attachments, comments, and multiple statements.
- Open the database in read-only mode.
- Apply row and execution-time limits.
- Return result metadata with every query: row count, column names, and data classification.
- Treat checked-in example data as fictional or synthetic unless a source explicitly says otherwise.

The model may generate a query, but the query tool owns enforcement.

## 5. Keep decision policy outside the model

Risk scoring, thresholds, budget allocation, and maintenance/retirement actions are policy. Implement them as deterministic, versioned code.

Each decision tool should return:

- formula or policy version
- normalized inputs
- component-level contributions
- final score or rank
- threshold selected
- confidence and missing evidence
- plain-language explanation

The model can select the tool and explain its output. It must not invent a new formula because the requested conclusion is inconvenient. Budget changes should alter phasing, not historical evidence or risk scores.

## 6. Execute generated code in a sandbox

Generated Python is valuable for calculations, charts, transformations, and exploratory analysis. It is also untrusted input.

Use one isolated workspace per run:

```text
create -> attest -> stage -> execute -> harvest -> delete
```

Minimum sandbox policy:

- no model-provider or database credentials
- outbound network blocked by default
- only staged data and prompt context available
- bounded CPU time, wall time, output size, and file size
- writable workspace and temporary directory only
- explicit artifact allowlist such as `.csv`, `.json`, `.md`, `.png`, and `.ipynb`
- artifact manifest with size and SHA-256
- cleanup in `finally`, including errors and cancellation

Sandboxing limits blast radius; it does not prove that generated analysis is correct. Evaluation must independently verify calculations, labels, file signatures, and conclusions.

## 7. Separate evidence levels

ALM systems often join evidence with different semantics: installed-asset records, maintenance events, product/model signals, fleet aggregates, regulatory records, and generated analysis.

Carry the evidence level with every record:

- **asset-level** — directly linked to an installed asset identifier
- **model-level** — linked to manufacturer/model but not an installed unit
- **product-class-level** — aggregate evidence used only as contextual signal
- **inferred** — generated interpretation that requires review

Do not collapse model-level or product-level signals into asset-level causality. Do not calculate failure or incident rates without a valid exposure denominator. Make source URLs, retrieval timestamps, match confidence, and unresolved identity ambiguity visible in the answer.

## 8. Replace shared-folder memory with run-scoped artifacts

A shared directory with filenames passed in natural language is not durable memory. Use a run-scoped workspace and artifact registry.

```text
output/agent-runs/<run-id>/
    run.json
    tool-events.jsonl
    artifacts.json
    analysis.csv
    visualization.png
```

`run.json` should record the query, model, configuration version, tool trajectory, latency, errors, and final answer. `artifacts.json` should record file type, size, checksum, producing tool, and harvest status.

Pass structured references between tools. Never rely on “the newest file” or a filename derived from untrusted user text.

## 9. Gate implementation on model and tool-calling verification

Before debugging the workflow, prove that the selected model endpoint supports the required behavior:

1. Resolve the exact model identifier from the endpoint.
2. Run a basic completion smoke test with a deterministic expected response.
3. Force a dummy function call and validate its JSON arguments.
4. Fail closed if the requested model or tool calling is unavailable.
5. Do not silently switch endpoints or models.

Load credentials at runtime from a secret manager or OS credential store. Inject them only into the agent host process and never persist or forward them into the sandbox.

## 10. Use configuration for composition

The runtime configuration should declare the model, tools, MCP groups, sandbox policy, artifact registry, and workflow entry point.

```yaml
workflow:
  _type: alm_deep_agent
  llm: primary_model
  sandbox: analysis_sandbox
  tools:
    - describe_asset_database
    - query_asset_database
    - search_asset_events
    - regulatory_evidence
    - score_lifecycle_risk
    - build_replacement_plan
```

Configuration should compose independently testable components. Domain rules stay in code; secrets stay outside YAML; prompts define behavior but do not replace enforcement.

Use MCP when a capability has an independent lifecycle, ownership boundary, or reuse case. Keep simple local capabilities as function tools.

## 11. Make evaluations the executable specification

Create the evaluation set before tuning prompts. Include easy lookups, multi-tool decisions, generated-code analyses, adversarial attribution questions, and budget-constrained planning.

Each case should define:

- `id`, `question`, `level`, and `category`
- reference facts and numeric tolerances
- required and prohibited tools
- forbidden claims and required disclaimers
- expected artifacts and file signatures
- required execution boundary, such as sandbox use

Grade behavior rather than prose similarity:

| Dimension | What to verify |
|---|---|
| Trajectory | Required tools called; prohibited tools absent |
| Facts | IDs, counts, dates, scores, and budget totals |
| Calculations | Values within explicit tolerances |
| Safety | Forbidden attribution or denominator-free claims absent |
| Artifacts | Expected names, types, signatures, and non-empty content |
| Cleanup | No sandbox or temporary secret remains |

Include at least one mandatory safety refusal and two mandatory generated-code cases that produce machine-verifiable artifacts.

## 12. Add observability at the trust boundaries

Capture traces for model requests, tool calls, MCP calls, sandbox lifecycle events, artifact harvesting, retries, and finalization.

Useful fields include:

- run and trace IDs
- model and prompt/configuration versions
- tool name, structured arguments, duration, and status
- source URLs and evidence match tier
- sandbox policy digest and attestation result
- artifact names and checksums
- retry and failure reason

Redact credentials and sensitive data before logging. Auditability is a data contract, not a promise that raw model traces will be understandable later.

## 13. Migrate incrementally

1. **Freeze expected behavior** — write evaluation cases for the current SQL and plotting paths.
2. **Extract capabilities** — convert SQL, evidence retrieval, scoring, planning, and plotting into independently testable tools.
3. **Introduce one query-driven agent** — pass the real user query and let the model select tools dynamically.
4. **Move code execution into the sandbox** — stage inputs, harvest allowlisted artifacts, and guarantee cleanup.
5. **Add external tool boundaries** — expose independently owned services through MCP when justified.
6. **Add specialized models selectively** — anomaly and RUL services return only after their validation data and evaluations exist.
7. **Add subagents only with evidence** — require measurable gains that justify extra coordination cost, latency, and failure modes.

## 14. Avoid these failure modes

- A dashboard that bypasses the agent and directly calls deterministic backend routes.
- A fixed “call every tool” workflow presented as autonomous reasoning.
- Generated scoring formulas or thresholds that change between runs.
- External product-level evidence presented as proof about a specific asset.
- Code execution on the host process or with inherited credentials.
- Shared filenames used as implicit memory between agents.
- Empty tool errors that prevent self-correction.
- A judge-model-only evaluation with no deterministic checks.
- Adding subagents because the architecture diagram looks more agentic.

## Completion checklist

- [ ] A real query reaches the selected model.
- [ ] The model dynamically selects only the tools needed for the question.
- [ ] Database access is schema-aware, read-only, and bounded.
- [ ] Decision policy is deterministic, versioned, and explainable.
- [ ] Generated code runs only in an isolated, credential-free sandbox.
- [ ] Artifacts are run-scoped, allowlisted, hashed, harvested, and cleaned up.
- [ ] Evidence retains its source, granularity, timestamp, and confidence.
- [ ] Evaluations verify trajectories, facts, calculations, safety, artifacts, and cleanup.
- [ ] Model completion and structured tool calling pass before end-to-end testing.
- [ ] Live integrations fail explicitly or use a clearly labelled fallback.
- [ ] Human review remains the final action boundary for consequential decisions.

