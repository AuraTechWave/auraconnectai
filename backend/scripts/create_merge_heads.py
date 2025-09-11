#!/usr/bin/env python3
"""Create a merge migration to consolidate multiple Alembic heads.

This script scans alembic/versions, detects heads, and writes a merge script
that declares all detected heads as its down_revisions. It does NOT run Alembic.

Usage:
  python backend/scripts/create_merge_heads.py [--dry-run]

The generated file follows the repository's timestamped naming pattern.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path
from typing import Dict, List, Optional


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def parse_migration(file_path: Path) -> Optional[Dict[str, str]]:
    text = file_path.read_text(encoding="utf-8")
    rev_match = re.search(r"revision(?:\s*:\s*str)?\s*=\s*['\"]([^'\"]+)['\"]", text)
    down_match = re.search(
        r"down_revision(?:\s*:\s*Union\[str,\s*None\])?\s*=\s*['\"]([^'\"]+)['\"]",
        text,
    )
    if not rev_match:
        return None
    return {
        "revision": rev_match.group(1),
        "down_revision": down_match.group(1) if down_match else None,
        "file": file_path.name,
    }


def find_heads() -> List[str]:
    migrations: Dict[str, Dict[str, str]] = {}
    children: Dict[str, List[str]] = {}

    for p in VERSIONS_DIR.glob("*.py"):
        if p.name == "__pycache__":
            continue
        parsed = parse_migration(p)
        if not parsed:
            continue
        rev = parsed["revision"]
        down = parsed["down_revision"]
        migrations[rev] = parsed
        if down and down != "None":
            children.setdefault(down, []).append(rev)

    # A head is any revision that no migration lists as its down_revision
    heads = [rev for rev in migrations.keys() if rev not in children]
    return heads


def generate_merge_filename() -> str:
    now = dt.datetime.utcnow()
    return now.strftime("%Y%m%d_%H%M_merge_heads.py")


def write_merge_script(heads: List[str], filename: str, dry_run: bool = False) -> Path:
    revision = filename.replace(".py", "")
    # Use down_revision tuple if more than one head; else single string
    if len(heads) == 1:
        down_line = f"down_revision = '{heads[0]}'\n"
    else:
        joined = ", ".join([f"'{h}'" for h in heads])
        down_line = f"down_revision = ({joined})\n"

    content = f"""# Auto-generated merge migration
# Created by create_merge_heads.py

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '{revision}'
{down_line}branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration; no schema changes.
    pass


def downgrade():
    # This is a merge migration; no schema changes.
    pass
"""

    out_path = VERSIONS_DIR / filename
    if dry_run:
        print("[DRY RUN] Would write:", out_path)
        print(content)
        return out_path
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Do not write file")
    args = parser.parse_args()

    if not VERSIONS_DIR.exists():
        print(f"Versions directory not found: {VERSIONS_DIR}")
        return 1

    heads = find_heads()
    if len(heads) <= 1:
        print("No merge required; found", len(heads), "head(s)")
        return 0

    print(f"Detected {len(heads)} heads:")
    for h in heads:
        print(" -", h)

    filename = generate_merge_filename()
    path = write_merge_script(heads, filename, dry_run=args.dry_run)
    print("Wrote merge migration:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
