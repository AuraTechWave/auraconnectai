#!/usr/bin/env python3
"""Bulk GitHub issue creator using the GitHub CLI.

Usage:
    python scripts/create_github_issues.py path/to/issues.yaml

The YAML file should contain keys:
    repo: owner/repo (can be overridden via --repo)
    default_labels: [optional list applied to every issue]
    issues:
      - title: "Issue title"
        body: |
          Markdown body
        labels: [optional additional labels]
        assignees: [optional list of GitHub usernames]
        milestone: optional milestone name or number

The script shells out to `gh issue create`, so you must have `gh` installed
and authenticated (`gh auth login`).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover - missing dependency
    yaml = None
    YAML_IMPORT_ERROR = exc
else:
    YAML_IMPORT_ERROR = None


def load_issue_spec(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required. Install it with `pip install pyyaml` before running this script."  # noqa: E501
        ) from YAML_IMPORT_ERROR

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Root of {path} must be a mapping")
    return data


def unique(seq: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in seq:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def build_command(
    issue: Dict[str, Any], repo: str, default_labels: Sequence[str]
) -> Tuple[List[str], Optional[str]]:
    title = issue.get("title")
    if not title:
        raise ValueError("Every issue entry must have a title")

    body = issue.get("body", "")
    labels = unique(list(default_labels) + list(issue.get("labels", []) or []))
    assignees = unique(issue.get("assignees", []) or [])
    milestone = issue.get("milestone")

    cmd: List[str] = [
        "gh",
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
    ]

    for label in labels:
        cmd.extend(["--label", label])
    for assignee in assignees:
        cmd.extend(["--assignee", assignee])
    if milestone:
        cmd.extend(["--milestone", str(milestone)])

    body_file = None
    if body:
        tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        tmp.write(body)
        tmp.flush()
        tmp.close()
        body_file = tmp.name
        cmd.extend(["--body-file", body_file])
    else:
        cmd.extend(["--body", ""])

    return cmd, body_file


def run_commands(commands: List[Tuple[List[str], Optional[str]]], dry_run: bool) -> None:
    for cmd, body_file in commands:
        if dry_run:
            printable = " ".join(f'"{part}"' if " " in part else part for part in cmd)
            print(f"[dry-run] {printable}")
            if body_file:
                Path(body_file).unlink(missing_ok=True)
            continue

        try:
            subprocess.run(cmd, check=True)
        finally:
            if body_file:
                Path(body_file).unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bulk create GitHub issues via gh CLI")
    parser.add_argument("spec", type=Path, help="Path to YAML issue specification")
    parser.add_argument("--repo", help="Override repo (owner/name)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")

    args = parser.parse_args(argv)

    data = load_issue_spec(args.spec)
    repo = args.repo or data.get("repo")
    if not repo:
        parser.error("Repository must be provided either in YAML under 'repo' or via --repo")

    default_labels = data.get("default_labels", []) or []
    if not isinstance(default_labels, list):
        raise ValueError("default_labels must be a list if provided")

    issues = data.get("issues")
    if not issues or not isinstance(issues, list):
        raise ValueError("issues must be a non-empty list")

    commands: List[Tuple[List[str], Optional[str]]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            raise ValueError("Each issue entry must be a mapping")
        cmd, body_file = build_command(issue, repo, default_labels)
        commands.append((cmd, body_file))

    run_commands(commands, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
