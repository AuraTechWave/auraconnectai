#!/usr/bin/env python3
"""Script to fix all migration reference issues"""

import os
import re
from pathlib import Path

def extract_revision_id(content):
    """Extract the revision ID from migration file content"""
    match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1) if match else None

def extract_down_revision(content):
    """Extract the down_revision ID from migration file content"""
    match = re.search(r"down_revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1) if match else None

def main():
    migrations_dir = Path("alembic/versions")
    if not migrations_dir.exists():
        print("Error: alembic/versions directory not found")
        return
    
    # Collect all migrations
    migrations = {}
    references = {}
    
    for file_path in migrations_dir.glob("*.py"):
        if file_path.name == "__pycache__":
            continue
            
        content = file_path.read_text()
        revision = extract_revision_id(content)
        down_revision = extract_down_revision(content)
        
        if revision:
            migrations[revision] = {
                'file': file_path.name,
                'down_revision': down_revision,
                'content': content
            }
            if down_revision and down_revision != 'None':
                references[down_revision] = references.get(down_revision, []) + [revision]
    
    print(f"\nFound {len(migrations)} migrations")
    print("\nMigrations with missing dependencies:")
    
    issues_found = False
    fixes_applied = []
    
    for revision, info in migrations.items():
        down_rev = info['down_revision']
        if down_rev and down_rev != 'None' and down_rev not in migrations:
            issues_found = True
            print(f"\n{info['file']}:")
            print(f"  - Revision: {revision}")
            print(f"  - References missing: {down_rev}")
            
            # Try to fix based on common patterns
            file_path = migrations_dir / info['file']
            content = info['content']
            
            # Check if the down_revision looks like it needs the full timestamp format
            if len(down_rev) == 4 and down_rev.isdigit():
                # Look for a migration with this number
                for other_rev, other_info in migrations.items():
                    if other_rev.endswith(f"_{down_rev}"):
                        print(f"  - Found matching migration: {other_rev}")
                        # Update the file
                        new_content = content.replace(f"down_revision = '{down_rev}'", f"down_revision = '{other_rev}'")
                        file_path.write_text(new_content)
                        fixes_applied.append(f"Fixed {info['file']}: {down_rev} -> {other_rev}")
                        break
    
    if not issues_found:
        print("No missing dependencies found!")
    
    print("\n\nAll migrations in order:")
    # Build dependency tree
    roots = [rev for rev in migrations if not migrations[rev]['down_revision'] or migrations[rev]['down_revision'] == 'None']
    
    def print_tree(rev, indent=0):
        info = migrations.get(rev)
        if info:
            print("  " * indent + f"- {rev} ({info['file']})")
            for child in references.get(rev, []):
                print_tree(child, indent + 1)
    
    for root in roots:
        print_tree(root)
    
    if fixes_applied:
        print("\n\nFixes applied:")
        for fix in fixes_applied:
            print(f"  - {fix}")

if __name__ == "__main__":
    main()