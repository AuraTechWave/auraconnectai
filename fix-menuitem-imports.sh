#!/bin/bash

# Fix all MenuItem imports to use core.menu_models

echo "🔧 Fixing MenuItem Imports"
echo "========================="

cd backend

# Find all files importing MenuItem from menu.models
echo "Finding and fixing MenuItem imports..."
find . -name "*.py" -type f -exec grep -l "from modules.menu.models import MenuItem" {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/from modules\.menu\.models import MenuItem/from core.menu_models import MenuItem/g' "$file"
done

# Also fix relative imports
find . -name "*.py" -type f -exec grep -l "from \.\.\.menu\.models import MenuItem" {} \; | while read file; do
    echo "  Fixing relative import in: $file"
    sed -i.bak 's/from \.\.\.menu\.models import MenuItem/from core.menu_models import MenuItem/g' "$file"
done

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ MenuItem import fixes applied!"