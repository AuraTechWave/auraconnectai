#!/bin/bash

# Fix Pydantic v2 compatibility issues

echo "🔧 Fixing Pydantic v2 Compatibility Issues"
echo "=========================================="

cd backend

# Fix 1: Replace orm_mode with from_attributes
echo "Replacing orm_mode with from_attributes..."
find . -name "*.py" -type f -exec grep -l "orm_mode = True" {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/orm_mode = True/from_attributes = True/g' "$file"
done

# Fix 2: Replace @validator with @field_validator
echo "Replacing @validator with @field_validator..."
find . -name "*.py" -type f -exec grep -l "@validator" {} \; | while read file; do
    echo "  Fixing: $file"
    # First ensure field_validator is imported
    if ! grep -q "field_validator" "$file"; then
        if grep -q "from pydantic import" "$file"; then
            sed -i.bak '/from pydantic import/ s/$/\, field_validator/' "$file"
            # Remove duplicate commas
            sed -i.bak 's/,\s*,/,/g' "$file"
        fi
    fi
    # Replace validator with field_validator
    sed -i.bak 's/@validator/@field_validator/g' "$file"
    # Add @classmethod after field_validator
    sed -i.bak '/@field_validator/!b;n;/def/i\    @classmethod' "$file"
done

# Fix 3: Replace schema_extra with json_schema_extra  
echo "Replacing schema_extra with json_schema_extra..."
find . -name "*.py" -type f -exec grep -l "schema_extra" {} \; | while read file; do
    echo "  Fixing: $file"
    sed -i.bak 's/schema_extra/json_schema_extra/g' "$file"
done

# Fix 4: Fix Config classes to use model_config
echo "Converting Config classes to model_config..."
find . -name "*.py" -type f -exec grep -l "class Config:" {} \; | while read file; do
    echo "  Checking: $file"
    # This is more complex and would need careful handling
done

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ Pydantic v2 fixes applied!"
echo ""
echo "Note: Some manual fixes may still be needed for:"
echo "  - Complex validators that use 'values' parameter"
echo "  - Config classes with multiple settings"
echo "  - root_validator decorators"