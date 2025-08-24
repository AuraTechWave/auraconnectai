#!/bin/bash

# Fix all cache_service imports

echo "🔧 Fixing cache_service Imports"
echo "==============================="

cd backend

# Find and fix all cache_service imports
echo "Finding and fixing cache_service imports..."
find . -name "*.py" -type f -exec grep -l "from core.cache import cache_service" {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/from core\.cache import cache_service/from core.cache import cache_manager as cache_service/g' "$file"
done

# Also check for other variations
find . -name "*.py" -type f -exec grep -l "from \.\.\.core\.cache import cache_service" {} \; | while read file; do
    echo "  Fixing relative import in: $file"
    sed -i.bak 's/from \.\.\.core\.cache import cache_service/from core.cache import cache_manager as cache_service/g' "$file"
done

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ cache_service import fixes applied!"