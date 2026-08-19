from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from healthcare_alm.models import ArtifactRef, SandboxResult
from healthcare_alm.sandbox.local import LocalSandboxRunner


def score_worker_source() -> str:
    return Path(__file__).with_name("openshell_score_worker.py").read_text()


class OpenShellSandboxRunner:
    """Execute scoring in an existing policy-governed OpenShell sandbox."""

    def __init__(self, sandbox_name: str, executable: str = "openshell", timeout_seconds: float = 30.0) -> None:
        if not sandbox_name:
            raise ValueError("An OpenShell sandbox name is required.")
        self.sandbox_name = sandbox_name
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    @classmethod
    def available(cls, executable: str = "openshell") -> bool:
        return shutil.which(executable) is not None

    def run_score(self, payload: dict, output_dir: Path) -> SandboxResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            self.executable,
            "sandbox",
            "exec",
            "-n",
            self.sandbox_name,
            "--timeout",
            str(round(self.timeout_seconds)),
            "--no-tty",
            "--",
            "python",
            "-c",
            score_worker_source(),
        ]
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds + 5,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return SandboxResult(
                status="timeout",
                provider="openshell",
                stdout=error.stdout or "",
                stderr=error.stderr or "",
                environment_keys=[],
            )
        if completed.returncode != 0:
            return SandboxResult(
                status="failed",
                provider="openshell",
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                environment_keys=[],
            )
        try:
            normalized = json.dumps(json.loads(completed.stdout), indent=2, sort_keys=True).encode()
        except json.JSONDecodeError as error:
            return SandboxResult(
                status="failed",
                provider="openshell",
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=f"Invalid scoring JSON: {error}",
                environment_keys=[],
            )
        path = output_dir / "score_result.json"
        path.write_bytes(normalized)
        artifact = ArtifactRef(
            artifact_id="score-result",
            path=path,
            media_type="application/json",
            sha256=hashlib.sha256(normalized).hexdigest(),
            size_bytes=len(normalized),
        )
        return SandboxResult(
            status="completed",
            provider="openshell",
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            environment_keys=[],
            artifacts=[artifact],
        )


def create_sandbox_runner(provider: str = "auto"):
    sandbox_name = os.environ.get("OPENSHELL_SANDBOX", "")
    openshell_ready = bool(sandbox_name) and OpenShellSandboxRunner.available()
    if provider == "openshell":
        if not openshell_ready:
            raise RuntimeError(
                "OpenShell requested but unavailable. Install the CLI and set OPENSHELL_SANDBOX to a running sandbox."
            )
        return OpenShellSandboxRunner(sandbox_name)
    if provider == "auto" and openshell_ready:
        return OpenShellSandboxRunner(sandbox_name)
    return LocalSandboxRunner()
