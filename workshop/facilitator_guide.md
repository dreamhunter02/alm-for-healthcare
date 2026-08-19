# Facilitator Guide — 60-Minute Technical Workshop

## Outcome

Attendees can explain how one AI-Q Deep Agent combines hospital records, FDA evidence, deterministic decision tools, and sandboxed Python to answer medical-device lifecycle questions without treating the LLM as the decision rule.

## Before the room (10 minutes)

1. Start Colima and verify `.venv/bin/openshell sandbox list` returns successfully.
2. Run `.venv/bin/python scripts/run_with_env.py .venv/bin/nat validate --config_file configs/config_aiq_agent.yml`.
3. Run the Q08 query once and keep its answer, CSV, PNG, and `run.json` open as the fallback.
4. Open `workshop/Agents_in_Healthcare_ALM_Technical_Workshop.pptx` in presentation mode.

## Agenda

| Time | Activity | Point to land |
|---:|---|---|
| 0–15 | Fleet scale, systems, and MAUDE | Retirement is an evidence-joining problem; MAUDE is a safety signal, not incidence or unit causality. |
| 15–28 | Synthetic hospital dataset + PUMP-009 | Synthetic local records make the workshop reproducible while preserving the real joins and governance boundary. |
| 28–43 | AI-Q architecture, tools, and decision boundaries | The LLM chooses actions; SQL, scoring, and budget tools keep authoritative logic outside the model. |
| 43–52 | OpenShell execution + observed analyses | Generated code becomes useful when execution is isolated, artifacted, and cleaned up. |
| 52–60 | Live query, audit trail, and CTA | Show one complete query-to-artifact trace, then point attendees to the repo and evaluation set. |

## Demo talk track

1. Submit the Q08 correlation query through `nat run`. While it runs: “The query—not a dashboard route—drives tool selection.”
2. In the trace, show schema inspection → read-only SQL → sandbox file write → Python execution.
3. Open `correlation_analysis.csv` and `utilization_vs_maintenance.png`; connect `r = 0.9495` to the actual tool outputs.
4. Ask Q07 as the safety contrast. The correct answer refuses PUMP-009 unit causality because MAUDE has no unit linkage or denominator.
5. Close with Q09: risk scoring and budget phasing are deterministic; the LLM assembles evidence and explains the recommendation.

## Questions to provoke

- Which hospital-specific signals would you add before a real POC: repair parts, cybersecurity support, utilization, loaners, or clinical criticality?
- Which threshold needs governance approval rather than model tuning?
- When should an unavailable recall service block a recommendation instead of lowering confidence?
- What belongs in OpenShell versus a read-only host tool?

## Closing frame

The reusable pattern is query → evidence tools → deterministic decision tools → isolated computation → cited answer. Swap the inventory schema and evidence adapters while keeping the safety, scoring, planning, and audit contracts.
