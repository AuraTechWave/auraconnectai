#!/usr/bin/env python3
"""
Fix await require_permission usage - it should not be awaited
"""
import os
import re

files_to_fix = [
    'modules/analytics/routers/pos/export_routes.py',
    'modules/analytics/routers/pos/details_routes.py',
    'modules/analytics/routers/pos/alerts_routes.py',
    'modules/analytics/routers/pos/dashboard_routes.py',
]

for file_path in files_to_fix:
    full_path = os.path.join(os.path.dirname(__file__), file_path)
    if os.path.exists(full_path):
        with open(full_path, 'r') as f:
            content = f.read()
        
        # Remove await from require_permission calls
        content = re.sub(r'await require_permission\(', 'require_permission(', content)
        
        with open(full_path, 'w') as f:
            f.write(content)
        
        print(f"Fixed {file_path}")
    else:
        print(f"File not found: {file_path}")