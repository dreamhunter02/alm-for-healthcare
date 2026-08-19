#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

from healthcare_alm.repository_hygiene import scan_paths


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    findings = scan_paths([root / name for name in names if name])
    if findings:
        for finding in findings:
            print(f"FAIL {finding.category}: {finding.path.relative_to(root)}")
        return 1
    print(f"PASS: {len([name for name in names if name])} tracked files contain no blocked identity or secret patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
