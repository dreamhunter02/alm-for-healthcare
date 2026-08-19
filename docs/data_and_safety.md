# Data and Safety Notes

## Data used

- Public events: [openFDA device event endpoint](https://api.fda.gov/device/event.json), filtered to product code `FRN`.
- Public recalls: [openFDA device recall endpoint](https://api.fda.gov/device/recall.json), filtered to `FRN`.
- Local context: 12 fictional infusion pumps + fictional maintenance records under `data/`.
- Device classification: `FRN` — infusion pump, FDA Class II, regulation `21 CFR 880.5725`.

Cached records preserve openFDA identifiers, dates, report type, manufacturer/model text, source query URL, last-updated metadata, and the FDA disclaimer.

## Evidence hierarchy

1. Normalized manufacturer + exact model → high confidence.
2. Manufacturer + brand token overlap → medium confidence.
3. Same product code only → low confidence and capped public-signal points.

Recall matches require manufacturer plus model/brand evidence. Product-code membership alone is never reported as a recall match.

## What the score means

The score prioritizes fictional fleet review. It is not a failure probability, clinical incidence estimate, diagnosis, recall determination, or order to remove equipment from service.

Thresholds (`>=70` retire, `50–69` plan replacement, `<50` maintain) are workshop policy assumptions. A hospital would govern them with clinical engineering, safety, procurement, finance, and compliance owners.

## Production gaps

- Validate serial/model normalization against CMMS master data.
- Add denominators such as utilization + installed base before any rate analysis.
- Add manufacturer end-of-support, parts availability, cybersecurity, and clinical criticality.
- Require approved human workflow + immutable audit storage before operational use.
- Perform bias, robustness, data-quality, security, privacy, and regulatory review.

