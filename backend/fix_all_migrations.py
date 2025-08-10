#!/usr/bin/env python3
"""Script to fix all migration reference issues comprehensively"""

import os
import re
from pathlib import Path

def extract_revision_id(content):
    """Extract the revision ID from migration file content"""
    # Match both regular assignment and type-annotated assignment
    match = re.search(r"revision(?:\s*:\s*str)?\s*=\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1) if match else None

def extract_down_revision(content):
    """Extract the down_revision ID from migration file content"""
    # Match both regular assignment and type-annotated assignment
    match = re.search(r"down_revision(?:\s*:\s*Union\[str,\s*None\])?\s*=\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1) if match else None

def main():
    migrations_dir = Path("alembic/versions")
    if not migrations_dir.exists():
        print("Error: alembic/versions directory not found")
        return
    
    # Collect all migrations
    migrations = {}
    
    for file_path in migrations_dir.glob("*.py"):
        if file_path.name == "__pycache__":
            continue
            
        content = file_path.read_text()
        revision = extract_revision_id(content)
        down_revision = extract_down_revision(content)
        
        if revision:
            migrations[revision] = {
                'file': file_path,
                'file_name': file_path.name,
                'down_revision': down_revision,
                'content': content
            }
    
    print(f"\nFound {len(migrations)} migrations")
    
    # Create a mapping of all possible revision formats
    revision_mapping = {}
    for rev in migrations:
        # Map full revision to itself
        revision_mapping[rev] = rev
        
        # If revision has timestamp format, also map the suffix
        match = re.match(r'(\d{8}_\d{4}_)?(.+)', rev)
        if match and match.group(1):
            suffix = match.group(2)
            revision_mapping[suffix] = rev
    
    print("\nFixing migration references...")
    fixes_applied = []
    
    for revision, info in migrations.items():
        down_rev = info['down_revision']
        if down_rev and down_rev != 'None':
            # Check if down_revision needs to be mapped
            if down_rev not in migrations and down_rev in revision_mapping:
                correct_rev = revision_mapping[down_rev]
                if correct_rev != down_rev:
                    file_path = info['file']
                    content = info['content']
                    
                    # Fix the reference
                    # Handle both regular and type-annotated assignments
                    old_pattern1 = f"down_revision = '{down_rev}'"
                    new_pattern1 = f"down_revision = '{correct_rev}'"
                    old_pattern2 = f'down_revision: Union[str, None] = \'{down_rev}\''
                    new_pattern2 = f'down_revision: Union[str, None] = \'{correct_rev}\''
                    
                    if old_pattern1 in content:
                        new_content = content.replace(old_pattern1, new_pattern1)
                    else:
                        new_content = content.replace(old_pattern2, new_pattern2)
                    
                    if new_content != content:
                        file_path.write_text(new_content)
                        fixes_applied.append(f"Fixed {info['file_name']}: {down_rev} -> {correct_rev}")
    
    if fixes_applied:
        print("\n\nFixes applied:")
        for fix in fixes_applied:
            print(f"  - {fix}")
    else:
        print("\nNo fixes needed!")
    
    # Check for any remaining issues
    print("\n\nChecking for remaining issues...")
    issues_found = False
    
    # Re-read all migrations after fixes
    migrations = {}
    for file_path in migrations_dir.glob("*.py"):
        if file_path.name == "__pycache__":
            continue
            
        content = file_path.read_text()
        revision = extract_revision_id(content)
        down_revision = extract_down_revision(content)
        
        if revision:
            migrations[revision] = {
                'file_name': file_path.name,
                'down_revision': down_revision
            }
    
    for revision, info in migrations.items():
        down_rev = info['down_revision']
        if down_rev and down_rev != 'None' and down_rev not in migrations:
            issues_found = True
            print(f"\n{info['file_name']}:")
            print(f"  - Revision: {revision}")
            print(f"  - References missing: {down_rev}")
    
    if not issues_found:
        print("All migration references are valid!")

if __name__ == "__main__":
    main()