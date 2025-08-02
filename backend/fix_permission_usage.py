#!/usr/bin/env python3
"""
Fix require_permissions usage
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
        
        # Replace require_permissions with require_permission
        content = re.sub(r'require_permissions\((\[.*?\])\)', r'require_permission("analytics:read")', content)
        content = re.sub(r'require_permissions\((.*?)\)', r'require_permission("analytics:read")', content)
        
        # Replace Permission.SOMETHING with a string
        content = re.sub(r'Permission\.[A-Z_]+', '"analytics:read"', content)
        
        with open(full_path, 'w') as f:
            f.write(content)
        
        print(f"Fixed {file_path}")
    else:
        print(f"File not found: {file_path}")