#!/usr/bin/env python3
"""Analyze migration heads and chains"""

import os
from pathlib import Path
import re

migrations_dir = Path("alembic/versions")
migrations = {}
children = {}

for file_path in migrations_dir.glob("*.py"):
    if file_path.name == "__pycache__":
        continue
    
    content = file_path.read_text()
    
    # Extract revision
    rev_match = re.search(r"revision(?:\s*:\s*str)?\s*=\s*['\"]([^'\"]+)['\"]", content)
    revision = rev_match.group(1) if rev_match else None
    
    # Extract down_revision
    down_match = re.search(r"down_revision(?:\s*:\s*Union\[str,\s*None\])?\s*=\s*['\"]([^'\"]+)['\"]", content)
    down_revision = down_match.group(1) if down_match else None
    
    if revision:
        migrations[revision] = {
            'file': file_path.name,
            'down_revision': down_revision
        }
        
        if down_revision and down_revision != 'None':
            if down_revision not in children:
                children[down_revision] = []
            children[down_revision].append(revision)

# Find heads (revisions that are not down_revisions of any other migration)
heads = []
for rev in migrations:
    if rev not in children:
        heads.append(rev)

print(f"Found {len(heads)} heads:")
for head in sorted(heads):
    print(f"  - {head} ({migrations[head]['file']})")
    
# Find the most recent common ancestor
print("\nAnalyzing branches...")
def find_ancestors(rev):
    ancestors = []
    current = rev
    while current and current in migrations:
        ancestors.append(current)
        current = migrations[current]['down_revision']
        if current == 'None':
            break
    return ancestors

# For each head, trace back to find common ancestors
if len(heads) > 1:
    print("\nFinding common ancestors...")
    all_ancestors = []
    for head in heads:
        ancestors = find_ancestors(head)
        all_ancestors.append(ancestors)
        print(f"\n{head} ancestry ({len(ancestors)} migrations):")
        for i, anc in enumerate(ancestors[:5]):  # Show first 5
            print(f"  {i}: {anc}")
        if len(ancestors) > 5:
            print(f"  ... and {len(ancestors) - 5} more")
    
    # Find common ancestors
    common = set(all_ancestors[0])
    for ancestors in all_ancestors[1:]:
        common = common.intersection(set(ancestors))
    
    if common:
        print(f"\nFound {len(common)} common ancestors")
        # Find the most recent common ancestor
        for anc_list in all_ancestors:
            for anc in anc_list:
                if anc in common:
                    print(f"Most recent common ancestor: {anc}")
                    break
            break

# Suggest merge migration
print("\n\nTo fix this, create a merge migration:")
print("alembic merge -m 'merge_heads' " + " ".join(heads[:2]))