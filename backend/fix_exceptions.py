#!/usr/bin/env python3
"""
Replace custom exceptions with standard Python exceptions
"""
import os
import re
from pathlib import Path

def fix_file(file_path):
    """Fix exceptions in a single file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Replace the imports
        content = re.sub(
            r'from core\.exceptions import.*\n?',
            '',
            content
        )
        
        # Replace exception usage
        content = content.replace('NotFoundError', 'KeyError')
        content = content.replace('ValidationError', 'ValueError')
        content = content.replace('PermissionError', 'PermissionError')  # This one is standard
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"Fixed {file_path}")
            return True
        return False
        
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

# Files to fix
files_to_fix = [
    'modules/feedback/routers/reviews_router.py',
    'modules/feedback/routers/feedback_router.py',
    'modules/feedback/services/feedback_service.py',
    'modules/feedback/services/review_service.py',
    'modules/feedback/tests/test_review_service.py',
    'modules/analytics/services/pos/base_service.py',
    'modules/analytics/services/pos_alerts_service.py',
    'modules/analytics/services/pos_export_service.py',
    'modules/analytics/tests/test_negative_cases.py',
    'modules/analytics/tests/test_sales_report_service.py',
]

print("Fixing core.exceptions imports...")

for file_path in files_to_fix:
    full_path = os.path.join(os.path.dirname(__file__), file_path)
    if os.path.exists(full_path):
        fix_file(full_path)
    else:
        print(f"File not found: {file_path}")

print("Done!")