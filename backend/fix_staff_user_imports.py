#!/usr/bin/env python3
"""
Fix get_current_staff_user imports to use get_current_user
"""
import os
import re

files_to_fix = [
    'modules/feedback/routers/feedback_router.py',
    'modules/feedback/routers/reviews_router.py',
    'modules/feedback/tests/test_api_endpoints.py',
    'modules/ai_recommendations/routers/pricing_router.py',
    'modules/ai_recommendations/routers/staffing_router.py',
    'modules/analytics/tests/test_analytics_api.py',
]

for file_path in files_to_fix:
    full_path = os.path.join(os.path.dirname(__file__), file_path)
    if os.path.exists(full_path):
        with open(full_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Replace the import
        content = content.replace('get_current_staff_user', 'get_current_user')
        
        if content != original_content:
            with open(full_path, 'w') as f:
                f.write(content)
            print(f"Fixed {file_path}")
    else:
        print(f"File not found: {file_path}")

print("Done!")