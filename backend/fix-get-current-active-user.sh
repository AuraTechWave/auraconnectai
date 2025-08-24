#!/bin/bash

# Fix all get_current_active_user imports

echo "🔧 Fixing get_current_active_user imports"
echo "========================================"

cd backend

# Find and fix all get_current_active_user imports
echo "Finding and fixing get_current_active_user imports..."
find . -name "*.py" -type f -exec grep -l "from core.auth import.*get_current_active_user" {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/get_current_active_user/get_current_user/g' "$file"
done

# Also check for other variations
find . -name "*.py" -type f -exec grep -l "from \\.\\.\\.core\\.auth import.*get_current_active_user" {} \; | while read file; do
    echo "  Fixing relative import in: $file"
    sed -i.bak 's/get_current_active_user/get_current_user/g' "$file"
done

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ get_current_active_user import fixes applied!"