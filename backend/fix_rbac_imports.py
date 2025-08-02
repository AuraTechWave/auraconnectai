#!/usr/bin/env python3
"""
Fix core.rbac imports
"""
import os

files_to_fix = [
    'modules/analytics/routers/pos/export_routes.py',
    'modules/analytics/routers/pos/details_routes.py',
    'modules/analytics/routers/pos/alerts_routes.py',
]

for file_path in files_to_fix:
    full_path = os.path.join(os.path.dirname(__file__), file_path)
    if os.path.exists(full_path):
        with open(full_path, 'r') as f:
            content = f.read()
        
        # Replace the import
        content = content.replace('from core.rbac import require_permissions, Permission', 'from core.auth import require_permission')
        content = content.replace('from core.rbac import', 'from core.auth import')
        
        with open(full_path, 'w') as f:
            f.write(content)
        
        print(f"Fixed {file_path}")
    else:
        print(f"File not found: {file_path}")