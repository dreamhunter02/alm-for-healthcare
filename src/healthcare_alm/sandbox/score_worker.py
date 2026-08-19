from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE_ROOT))

from healthcare_alm.analysis.scoring import score_asset  # noqa: E402
from healthcare_alm.models import AssetEvidence, ScoreConfig  # noqa: E402


def main(input_path: Path, output_path: Path) -> None:
    payload = json.loads(input_path.read_text())
    if "evidence" in payload:
        evidence = AssetEvidence.model_validate(payload["evidence"])
        config = ScoreConfig.model_validate(payload.get("config", {}))
        result = score_asset(evidence, config).model_dump(mode="json")
    else:
        result = payload
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
