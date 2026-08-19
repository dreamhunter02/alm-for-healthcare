"""Pinned AI-Q v2.2.0-rc3 and Colima/OpenShell bootstrap."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

AIQ_VERSION = "2.2.0-rc3"
AIQ_ARCHIVE_URL = f"https://github.com/NVIDIA-AI-Blueprints/aiq/archive/refs/tags/v{AIQ_VERSION}.tar.gz"
AIQ_SHA256 = "93c5c6014e08390d7c80241b39919491fc2a9d260b6226c65c0aad96839c8228"
OPENSHELL_VERSION = "0.0.80"


def verify_sha256(path: Path, expected: str = AIQ_SHA256) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected:
        raise RuntimeError(f"AI-Q archive SHA-256 mismatch: expected {expected}, got {actual}")


def download_aiq(repo_root: Path) -> Path:
    vendor_dir = repo_root / ".vendor"
    archive = vendor_dir / f"aiq-v{AIQ_VERSION}.tar.gz"
    source_dir = vendor_dir / f"aiq-{AIQ_VERSION}"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        with urllib.request.urlopen(AIQ_ARCHIVE_URL, timeout=120) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
    verify_sha256(archive)
    if not source_dir.exists():
        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(vendor_dir, filter="data")
    if not source_dir.is_dir():
        raise RuntimeError(f"AI-Q archive did not produce {source_dir}")
    return source_dir


def _command(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def install_aiq_and_openshell(repo_root: Path, source_dir: Path) -> None:
    colima = shutil.which("colima") or "/opt/homebrew/bin/colima"
    bash = shutil.which("bash")
    homebrew_bash = Path("/opt/homebrew/bin/bash")
    if homebrew_bash.is_file():
        bash = str(homebrew_bash)
    if not bash or not Path(colima).is_file():
        raise RuntimeError("Colima and Bash 5 must be installed before running the AI-Q setup")
    if subprocess.run([colima, "status"], capture_output=True, check=False).returncode:
        _command([colima, "start"], cwd=repo_root)

    venv_dir = repo_root / ".venv"
    if not venv_dir.exists():
        _command([sys.executable, "-m", "venv", str(venv_dir)], cwd=repo_root)
    python = str(venv_dir / "bin/python")
    _command([python, "-m", "pip", "install", "uv"], cwd=repo_root)

    vendor_venv = source_dir / ".venv"
    if not vendor_venv.exists():
        vendor_venv.symlink_to(venv_dir, target_is_directory=True)
    policy_file = repo_root / "configs/openshell/generated/aiq-openshell-policy.yaml"
    _command(
        [
            bash,
            str(source_dir / "scripts/openshell/setup_openshell.sh"),
            "--openshell-version",
            OPENSHELL_VERSION,
            "--local-demo",
            "--policy",
            "offline",
            "--policy-file",
            str(policy_file),
        ],
        cwd=source_dir,
    )
    _command(
        [bash, str(source_dir / "scripts/openshell/install_gateway.sh"), "--colima", "--yes"],
        cwd=source_dir,
    )
    _command([python, "-m", "pip", "install", "-e", ".[dev]"], cwd=repo_root)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true", help="Verify and unpack AI-Q without installing it")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = download_aiq(repo_root)
    print(f"AI-Q {AIQ_VERSION} verified at {source_dir}")
    if not args.download_only:
        install_aiq_and_openshell(repo_root, source_dir)
        print("AI-Q + OpenShell 0.0.80 are ready on Colima")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
