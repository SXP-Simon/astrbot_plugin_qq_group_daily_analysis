"""Run pinned Python checks using the caller's dependency environment."""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run a check without modifying the caller's Python environment.

    Returns:
        The check's exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("lint", "format", "typecheck"))
    args, remaining = parser.parse_known_args()
    root = Path(__file__).resolve().parents[1]
    tool = "pyright" if args.check == "typecheck" else "ruff"
    requirement = next(
        line.strip()
        for line in (root / "requirements-tools.txt").read_text().splitlines()
        if line.startswith(f"{tool}==")
    )
    command = ["uv", "tool", "run", "--from", requirement, tool]
    if tool == "pyright":
        command.extend(["--pythonpath", sys.executable, *remaining])
    else:
        command.extend(["check" if args.check == "lint" else "format", *remaining])
    return subprocess.call(command, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
