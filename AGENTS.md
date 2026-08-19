# AGENTS.md

## Mission

Build and maintain a query-driven Asset Lifecycle Management Deep Agent for medical-device retirement planning.

The default path is:

```text
User query -> Nemotron Ultra -> healthcare tools -> OpenShell -> evidence-backed answer + artifacts
```

This is not a dashboard-first application and not a fixed seven-stage workflow. Keep one Deep Agent unless evaluations demonstrate that a subagent adds measurable value.

## Read first

1. `README.md` — supported setup and run commands.
2. `configs/config_aiq_agent.yml` — authoritative AI-Q composition.
3. `evaluation/agent_queries.json` — executable behavior specification.
4. `docs/data_and_safety.md` — evidence semantics and safety boundary.
5. `docs/alm_agent_modernization_guide.md` — reusable architecture principles.

## Authoritative boundaries

- The LLM selects tools and explains results; it does not define risk policy.
- `src/healthcare_alm/analysis/scoring.py` owns the versioned retirement-risk formula.
- `src/healthcare_alm/analysis/planner.py` owns budget-aware replacement phasing.
- `src/healthcare_alm/retrievers/sql.py` owns read-only SQL enforcement.
- `src/healthcare_alm/agent/domain.py` owns tool contracts and domain guardrails.
- `src/healthcare_alm/agent/deep_agent.py` owns DeepAgents/OpenShell orchestration and cleanup.
- `src/healthcare_alm/mcp/recall_server.py` owns the regulatory MCP boundary.
- `configs/openshell-policy.yml` owns the human-readable sandbox policy; setup generates the runtime policy.

Do not move deterministic policy into prompts. Do not bypass tool enforcement from the workflow.

## Data and safety rules

- Inventory and maintenance records checked into this repository are fictional workshop data.
- MAUDE and recall data are product/model-level public safety signals unless an explicit asset identifier proves otherwise.
- Never claim that a hospital asset caused a MAUDE event.
- Never calculate incidence or failure rates without a valid exposure denominator.
- Preserve FDA source URLs, evidence level, match tier, and retrieval metadata.
- Missing or unavailable evidence is not evidence of safety.
- Recommendations require human clinical-engineering review.
- Do not introduce PHI, patient records, clinical advice, or automated removal-from-service actions.

These rules must be enforced in tool code and evaluations, not only in the system prompt.

## Participant configuration and credentials

- `.env.example` defines the complete participant configuration contract.
- `.env` is local, gitignored, and should have file mode `0600`.
- Required variables: `NVIDIA_API_KEY`, `NVIDIA_API_BASE_URL`, and `NVIDIA_MODEL_NAME`.
- Use `scripts/run_with_env.py`; do not add OS-specific Keychain, credential-manager, username, or home-directory assumptions.
- Never print, log, commit, trace, cache, or copy `.env` values into artifacts.
- Never pass host credentials into OpenShell or Open WebUI.
- Tests involving secrets use dummy values and injected environments.

## Runtime

- Python: `>=3.11,<3.14`; the local reference environment uses `.venv`.
- AI-Q source: `v2.2.0-rc3`, pinned under gitignored `.vendor/` with SHA-256 verification.
- OpenShell: `0.0.80` on Colima.
- Model and endpoint are selected by `.env`; the example targets public NVIDIA API Catalog access.

Do not edit `.venv/`, `.vendor/`, generated OpenShell images, or installed packages directly. Update setup scripts and pins instead.

## Common commands

Setup and model gate:

```bash
python3.12 -m venv .venv
.venv/bin/python scripts/setup_aiq.py
.venv/bin/python scripts/verify_inference.py
```

Validate configuration:

```bash
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat validate --config_file configs/config_aiq_agent.yml
```

Run a query:

```bash
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat run \
  --config_file configs/config_aiq_agent.yml \
  --input "With a $50,000 budget, which pumps should we replace first?"
```

Run the generated-code path:

```bash
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat run \
  --config_file configs/config_aiq_agent.yml \
  --input "Use Python to calculate the fleet correlation and create a labeled PNG plot."
```

Tests and lint:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src tests scripts
```

Live evaluations:

```bash
.venv/bin/python scripts/evaluate_agent.py
```

Sandbox cleanup check:

```bash
.venv/bin/openshell sandbox list
```

## Tool behavior

### SQL

- Call `describe_hospital_database` before generated SQL.
- Accept one read-only `SELECT` or `WITH` statement only.
- Reject mutations, DDL, pragmas, attachments, comments, and multiple statements.
- Keep result metadata and the fictional-data classification.
- Return recoverable schema guidance so the model can retry.

### FDA evidence

- Normalize identifiers but keep raw provenance.
- Return source URLs and the openFDA disclaimer.
- Keep MAUDE event search and recall lookup independently replaceable.
- Treat product-code-only matches as contextual evidence, not asset evidence.

### Scoring and planning

- Use deterministic tools for risk scores and replacement phasing.
- Keep component inputs, points, policy version, action threshold, and explanation visible.
- A budget change may change phases; it must not rewrite evidence or risk.

### Generated code

- Use OpenShell for requested calculations, transformations, CSVs, notebooks, and plots.
- Stage only the minimum required rows and context.
- Block sandbox networking and withhold host credentials.
- Harvest only allowlisted artifacts up to configured limits.
- Finalize and delete the sandbox after success, error, timeout, or cancellation.
- Treat local macOS/Colima isolation as workshop-grade, not a production security boundary.

## Artifacts and observability

Agent runs belong under `output/agent-runs/<run-id>/` and evaluations under `output/evaluations/<timestamp>/`. Both roots are gitignored.

Preserve:

- query and final answer
- tool trajectory and timings
- source URLs and evidence metadata
- sandbox lifecycle and attestation state
- artifact names, sizes, and hashes
- failure and retry reasons

Never use a shared “latest file” as memory. Pass explicit run-scoped artifact references.

## Evaluation contract

`evaluation/agent_queries.json` is the executable specification. A new behavior is incomplete until its case defines:

- required tools and prohibited tools
- reference facts and numeric tolerances
- forbidden claims and required disclaimers
- artifact names, types, and signatures
- sandbox requirement when code execution is part of the answer

Q07 is the mandatory causality/denominator refusal. Q08 and Q10 are mandatory OpenShell artifact paths. Do not weaken these gates to improve pass rate.

## Change protocol

1. Inspect the nearest implementation and its tests before editing.
2. Add or update the evaluation case before changing agent behavior.
3. Keep tool descriptions precise enough for dynamic selection without encoding expected answers.
4. Add deterministic unit tests for enforcement and arithmetic.
5. Run focused tests, then the complete suite and Ruff.
6. For sandbox changes, verify attestation, artifact harvesting, and zero residual sandboxes.
7. For model/prompt changes, rerun the completion/tool-call gate and all ten live evaluations.

Do not add a frontend, fixed pipeline, model fallback, unrestricted host execution, or subagents unless the task explicitly requires it and evaluations cover the new behavior.

## Definition of done

A change is complete only when:

- the real CLI query reaches the agent
- required tools are selected dynamically
- authoritative logic remains deterministic
- safety claims respect evidence granularity
- generated code stays inside OpenShell
- artifacts are valid and harvested
- sandbox cleanup is proven
- tests and Ruff pass
- documentation and evaluation cases match the behavior
