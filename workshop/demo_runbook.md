# Demo Runbook

## Start here

```bash
colima status
.venv/bin/python scripts/check_repository_hygiene.py
.venv/bin/python scripts/verify_inference.py
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat validate --config_file configs/config_aiq_agent.yml
```

All four must pass before the workshop. `verify_inference.py` must report Nemotron Ultra completion and forced tool calling as `true`.

## Primary live query

```bash
.venv/bin/python scripts/run_with_env.py \
  .venv/bin/nat run \
  --config_file configs/config_aiq_agent.yml \
  --input "Create an ICU retirement plan under $50,000 using age, maintenance, and FDA evidence."
```

Success: PUMP-009 (74), PUMP-004 (53), PUMP-001 (42); the first two consume $48,000. The answer identifies fictional hospital data, model-level FDA evidence, and clinical-engineering review.

## Show generated code

Run Q08 from the README. Then open the newest folder under `output/agent-runs/` and show:

- `run.json` — query, dynamically selected tools, latency, artifacts, and failure reason
- `correlation_analysis.csv` — `r = 0.9495`
- `utilization_vs_maintenance.png` — generated inside OpenShell and harvested before cleanup

Confirm cleanup:

```bash
.venv/bin/openshell sandbox list
```

Expected: `No sandboxes found.`

## Recovery

| Symptom | Action |
|---|---|
| Colima stopped | Run `colima start` |
| Missing configuration | Copy `.env.example` to `.env`, then fill all required values |
| Key/model/tool-call gate fails | Verify the endpoint, model, and API key in `.env`; do not silently switch models |
| OpenShell gateway unavailable | Re-run `.venv/bin/python scripts/setup_aiq.py` |
| Model writes invalid SQL | The query tool returns schema retry guidance; rerun once if the model does not self-correct |
| Live FDA is unavailable | Cached FDA workshop fixtures remain deterministic; disclose cached provenance |

The old dashboard is not the demo path. Do not run `healthcare-alm serve` unless explicitly showing legacy code.
