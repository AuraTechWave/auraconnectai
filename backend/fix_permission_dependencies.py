#!/usr/bin/env python3
"""
Fix permission usage to be dependencies
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
        
        # Remove standalone require_permission calls
        content = re.sub(r'^\s*require_permission\("analytics:read"\)\s*$', '', content, flags=re.MULTILINE)
        
        # Add user dependency with permission check
        # Replace current_user: StaffMember = Depends(get_current_user)
        # with current_user: User = Depends(require_permission("analytics:read"))
        content = re.sub(
            r'current_user: StaffMember = Depends\(get_current_user\)',
            'current_user: User = Depends(require_permission("analytics:read"))',
            content
        )
        
        # Also replace StaffMember with User in imports
        content = content.replace('from modules.staff.models.staff_models import StaffMember', 'from core.auth import User')
        
        with open(full_path, 'w') as f:
            f.write(content)
        
        print(f"Fixed {file_path}")
    else:
        print(f"File not found: {file_path}")