from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from healthcare_alm.models import ArtifactRef, SandboxResult


class LocalSandboxRunner:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run_command(self, command: list[str], workdir: Path) -> SandboxResult:
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                env={},
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return SandboxResult(
                status="timeout",
                provider="local_subprocess",
                stdout=error.stdout or "",
                stderr=error.stderr or "",
                environment_keys=[],
            )
        return SandboxResult(
            status="completed" if completed.returncode == 0 else "failed",
            provider="local_subprocess",
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            environment_keys=[],
        )

    def run_score(self, payload: dict, output_dir: Path) -> SandboxResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        worker = Path(__file__).with_name("score_worker.py").resolve()
        with tempfile.TemporaryDirectory(prefix="healthcare-alm-score-") as temp:
            temp_dir = Path(temp)
            input_path = temp_dir / "input.json"
            sandbox_output = temp_dir / "score_result.json"
            input_path.write_text(json.dumps(payload, default=str))
            result = self.run_command(
                [sys.executable, "-I", str(worker), str(input_path), str(sandbox_output)], temp_dir
            )
            if result.status != "completed" or not sandbox_output.exists():
                return result
            destination = output_dir / "score_result.json"
            shutil.copy2(sandbox_output, destination)
        data = destination.read_bytes()
        artifact = ArtifactRef(
            artifact_id="score-result",
            path=destination,
            media_type="application/json",
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
        )
        return result.model_copy(update={"artifacts": [artifact]})
