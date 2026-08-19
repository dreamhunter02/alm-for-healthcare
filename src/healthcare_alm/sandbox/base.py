from __future__ import annotations

from pathlib import Path
from typing import Protocol

from healthcare_alm.models import SandboxResult


class SandboxRunner(Protocol):
    def run_score(self, payload: dict, output_dir: Path) -> SandboxResult: ...
