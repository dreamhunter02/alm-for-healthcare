#!/usr/bin/env python3
from __future__ import annotations

import json

from healthcare_alm.environment import load_workshop_environment
from healthcare_alm.inference import InferenceHubClient


def main() -> int:
    environment = load_workshop_environment()
    client = InferenceHubClient(
        environment["NVIDIA_API_KEY"],
        base_url=environment["NVIDIA_API_BASE_URL"],
    )
    try:
        print(json.dumps(client.verify(model_id=environment["NVIDIA_MODEL_NAME"]).as_dict(), indent=2))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
