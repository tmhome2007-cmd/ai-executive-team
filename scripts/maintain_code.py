#!/usr/bin/env python3
"""Format/check repository code and keep its source catalog synchronized."""

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["format", "check"])
    args = parser.parse_args()
    if importlib.util.find_spec("black") is None:
        raise SystemExit(
            "Install maintenance tools once: .venv/bin/python -m pip install -r requirements-maintenance.txt"
        )
    check = args.operation == "check"
    jobs = [
        ([sys.executable, "-m", "black", ".", *(["--check"] if check else [])], ROOT),
        (
            ["npm", "run", "format:check" if check else "format"],
            ROOT / "executive-dashboard",
        ),
        (
            [
                sys.executable,
                "scripts/code_catalog.py",
                *(["--check"] if check else []),
            ],
            ROOT,
        ),
    ]
    failed = False
    for command, directory in jobs:
        failed = (
            subprocess.run(command, cwd=directory, check=False).returncode != 0
            or failed
        )
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
