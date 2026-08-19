# Medical-Device Asset Lifecycle Management Agent

A workshop-ready AI-Q Deep Agent for medical-device retirement planning:

```text
Question → Nemotron → hospital/FDA tools → OpenShell Python → evidence-backed answer + artifacts
```

The hospital inventory and maintenance records are fictional. FDA MAUDE and recall records are model/product-level safety signals and do not prove that a specific hospital asset caused an event.

Workshop materials: [PowerPoint](workshop/Agents_in_Healthcare_ALM_Technical_Workshop.pptx) · [PDF](workshop/Agents_in_Healthcare_ALM_Technical_Workshop.pdf) · [facilitator guide](workshop/facilitator_guide.md) · [exercises](workshop/exercises.md)

## 1. Prerequisites

The automated local setup targets Apple Silicon macOS:

- Python 3.12
- Docker CLI
- [Colima](https://github.com/abiosoft/colima)
- Homebrew Bash 5
- NVIDIA API key from [build.nvidia.com](https://build.nvidia.com/)

AI-Q's included local OpenShell gateway installer is macOS-specific. Linux participants can use the same agent after connecting an operator-managed OpenShell gateway.

## 2. Configure the workshop

```bash
git clone <repository-url>
cd alm-for-healthcare
cp .env.example .env
chmod 600 .env
```

Open `.env` and fill in `NVIDIA_API_KEY`. The provided public NVIDIA endpoint and Nemotron model can be replaced with another accessible OpenAI-compatible NVIDIA endpoint/model pair.

Never commit `.env`. It is ignored by Git. The committed `.env.example` contains no credentials.

## 3. Install and verify

```bash
python3.12 -m venv .venv
.venv/bin/python scripts/setup_aiq.py
.venv/bin/python scripts/verify_inference.py
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat validate --config_file configs/config_aiq_agent.yml
```

Setup pins AI-Q `v2.2.0-rc3`, verifies its archive checksum, installs OpenShell `0.0.80`, starts Colima, builds the sandbox image, and installs this package.

## 4. Run the agent

CLI query:

```bash
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat run \
  --config_file configs/config_aiq_agent.yml \
  --input "With a $50,000 budget, which pumps should we replace first?"
```

Browser chat:

```bash
./scripts/start_open_webui.sh
```

Open <http://localhost:3000>, select `healthcare-alm`, and keep the launcher terminal open. Press `Ctrl-C` to stop, or run `./scripts/stop_open_webui.sh` from another terminal.

Generated files and audit records are written to `output/agent-runs/<run-id>/`. NVIDIA credentials remain in the host AI-Q process and are never passed into OpenShell or Open WebUI.

## Generated-code exercise

```bash
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat run \
  --config_file configs/config_aiq_agent.yml \
  --input "Use Python to calculate Pearson correlation between utilization hours and corrective maintenance count. Save correlation_analysis.csv and utilization_vs_maintenance.png."
```

Expected result: `r ≈ 0.9495`, a CSV, a PNG, an attested OpenShell sandbox, and no residual sandbox after completion.

## Repository map

```text
configs/       AI-Q and OpenShell configuration
data/          fictional inventory, maintenance, and cached FDA fixtures
evaluation/    ten-query behavior and safety specification
scripts/       setup, validation, launch, and evaluation commands
src/           agent, tools, scoring, FDA, MCP, and sandbox code
tests/         deterministic unit and integration tests
workshop/      slides, exercises, facilitator guide, and demo runbook
```

## Validation

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/python scripts/check_repository_hygiene.py
.venv/bin/python scripts/evaluate_agent.py
.venv/bin/openshell sandbox list
```

The live evaluation suite checks dynamic tool selection, expected facts, numeric tolerances, safety language, and generated artifact signatures.

## Safety boundary

- Do not introduce PHI or patient records.
- Do not claim unit-level causality from MAUDE or calculate failure rates without an exposure denominator.
- Deterministic tools own scoring and budget policy; the LLM explains results but does not invent policy.
- All replacement recommendations require clinical-engineering review.
- Local macOS/Colima isolation is workshop-grade, not a production security boundary.

Healthcare specialization of NVIDIA's original [Asset Lifecycle Management example](https://github.com/NVIDIA/GenerativeAIExamples/tree/main/industries/asset_lifecycle_management_agent), using [AI-Q `v2.2.0-rc3`](https://github.com/NVIDIA-AI-Blueprints/aiq/tree/v2.2.0-rc3).
