#!/usr/bin/env python3
from __future__ import annotations

import sys

from healthcare_alm.environment import EnvironmentConfigError, run_env_command


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_with_env.py COMMAND [ARG ...]", file=sys.stderr)
        return 2
    try:
        run_env_command(sys.argv[1:])
    except EnvironmentConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
