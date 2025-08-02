#!/usr/bin/env python3
"""
Fix analytics router to use User type instead of dict
"""
import re

filepath = "/Volumes/CodeMatrix/Projects/clones/auraconnectai/backend/modules/analytics/routers/analytics_router.py"

with open(filepath, 'r') as f:
    content = f.read()

# Replace all occurrences of current_user: dict with current_user: User
content = re.sub(r'current_user: dict = Depends', 'current_user: User = Depends', content)

with open(filepath, 'w') as f:
    f.write(content)

print(f"Fixed user type annotations in {filepath}")