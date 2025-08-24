#!/bin/bash

# Fix all metadata column issues in SQLAlchemy models

echo "🔧 Fixing SQLAlchemy metadata column issues"
echo "========================================"

cd backend

# Fix health_models.py
echo "Fixing modules/health/models/health_models.py..."
sed -i.bak 's/metadata = Column(JSON)/additional_metadata = Column("metadata", JSON)/g' modules/health/models/health_models.py

# Fix sms_models.py
echo "Fixing modules/sms/models/sms_models.py..."
sed -i.bak 's/metadata = Column(JSON)/additional_metadata = Column("metadata", JSON)/g' modules/sms/models/sms_models.py

# Fix notification_config_models.py
echo "Fixing modules/orders/models/notification_config_models.py..."
sed -i.bak 's/metadata = Column(JSON)/additional_metadata = Column("metadata", JSON)/g' modules/orders/models/notification_config_models.py

# Also need to fix references to the metadata attribute
echo ""
echo "Fixing references to metadata attribute..."

# Find and fix references to .metadata in these models
find . -name "*.py" -type f -exec grep -l "\.metadata\s*=" {} \; | while read file; do
    if grep -q "additional_metadata" "$file"; then
        echo "  Skipping $file (already fixed)"
    else
        echo "  Checking: $file"
        # Only fix if it's likely referring to our model's metadata
        grep -n "\.metadata\s*=" "$file" | grep -v "__table__" | grep -v "MetaData" || true
    fi
done

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ Metadata column fixes applied!"
echo ""
echo "Note: You may need to manually update any code that references the"
echo "old 'metadata' attribute to use 'additional_metadata' instead."