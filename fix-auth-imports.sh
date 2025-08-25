#!/bin/bash

# Fix all auth service imports

echo "🔧 Fixing Auth Service Imports"
echo "=============================="

cd backend

# Fix auth.services imports
echo "Fixing auth.services imports..."
find . -name "*.py" -type f -exec grep -l "from.*auth\.services.*import get_current_user" {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/from \.\.\.auth\.services\.auth_service import get_current_user/from core.auth import get_current_user/g' "$file"
    sed -i.bak 's/from modules\.auth\.services\.auth_service import get_current_user/from core.auth import get_current_user/g' "$file"
done

# Fix auth.models.User imports
echo "Fixing auth.models.User imports..."
find . -name "*.py" -type f -exec grep -l "from.*auth\.models import User" {} \; | while read file; do
    echo "  Fixing User import in: $file"
    sed -i.bak 's/from \.\.\.auth\.models import User/from core.rbac_models import RBACUser as User/g' "$file"
    sed -i.bak 's/from modules\.auth\.models import User/from core.rbac_models import RBACUser as User/g' "$file"
done

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ Auth import fixes applied!"