#!/bin/bash

# Fix common import issues in the backend

echo "🔧 Fixing Backend Import Issues"
echo "=============================="

cd backend

# Fix 1: Replace auth.models imports with rbac_models
echo "Fixing User model imports..."
find . -name "*.py" -type f -exec grep -l "from modules.auth.models import User" {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/from modules.auth.models import User/from core.rbac_models import RBACUser as User/g' "$file"
done

# Fix 2: Replace regex with pattern in pydantic fields
echo "Fixing pydantic regex to pattern..."
find . -name "*.py" -type f -exec grep -l 'regex=' {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/regex=/pattern=/g' "$file"
done

# Fix 3: Add missing TimestampMixin
echo "Adding TimestampMixin to database.py..."
if ! grep -q "class TimestampMixin" core/database.py; then
    cat >> core/database.py << 'EOF'


class TimestampMixin:
    """Mixin for adding created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
EOF
fi

# Fix 4: Add missing imports
echo "Adding missing imports..."

# Add datetime import to database.py if not present
if ! grep -q "from datetime import datetime" core/database.py; then
    sed -i.bak '1i\
from datetime import datetime' core/database.py
fi

# Add Column and DateTime imports if not present
if ! grep -q "from sqlalchemy import.*Column" core/database.py; then
    sed -i.bak '/from sqlalchemy.ext.declarative/i\
from sqlalchemy import Column, DateTime' core/database.py
fi

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ Import fixes applied!"
echo ""
echo "Now try starting the backend with:"
echo "  ./start-backend-minimal.sh"