# Hands-on Exercises

## 1. Budget is not risk (8 minutes)

1. Run `.venv/bin/healthcare-alm run --budget 120000 --output output/budget-120k`.
2. Run again with `--budget 50000 --output output/budget-50k`.
3. Compare `retirement_plan.csv` files.

Expected: risk scores stay identical; current-budget vs. next-horizon phases change.

## 2. Inspect the evidence cap (8 minutes)

1. Open `output/latest/bundle/audit.json`.
2. Compare PUMP-009 (`manufacturer_model`) with PUMP-007 (`product_code_only`).
3. Find the `maude_trend` + `event_severity_mix` score components.

Expected: broad product-code evidence is visible but capped; it cannot force retirement.

## 3. Break a dependency safely (8 minutes)

1. Run cached mode with networking disabled.
2. Confirm the same 12-device plan appears.
3. Review `fda_provenance` in the audit view.

Expected: cached evidence is explicit; no stage silently pretends it used live data.

## Stretch: add a device class

Copy the inventory schema, choose another openFDA product code, add its cached fixtures, then rerun the same seven contracts. Do not change the risk formula until the governance assumptions are documented.

