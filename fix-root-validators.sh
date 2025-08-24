#!/bin/bash

# Fix all root_validator issues

echo "🔧 Fixing Root Validators"
echo "========================"

cd backend

# Fix loyalty_schemas.py - already done manually

# Fix equipment_schemas_improved.py
echo "Fixing equipment_schemas_improved.py..."
if grep -q "@root_validator" modules/equipment/schemas/equipment_schemas_improved.py; then
    # Add model_validator import if not present
    if ! grep -q "model_validator" modules/equipment/schemas/equipment_schemas_improved.py; then
        sed -i.bak '/from pydantic import/ s/$/\, model_validator/' modules/equipment/schemas/equipment_schemas_improved.py
        sed -i.bak 's/,\s*,/,/g' modules/equipment/schemas/equipment_schemas_improved.py
    fi
    # Replace root_validator with model_validator
    sed -i.bak 's/@root_validator/@model_validator(mode='"'"'after'"'"')/g' modules/equipment/schemas/equipment_schemas_improved.py
    # Fix the method signature - change cls, values to self
    sed -i.bak '/@model_validator/,/return/ {
        s/def \([^(]*\)(cls, values)/def \1(self)/
        s/values\.get(/self./g
        s/values\[/self./g
        s/return values/return self/
    }' modules/equipment/schemas/equipment_schemas_improved.py
fi

# Fix payment_config.py
echo "Fixing payment_config.py..."
if grep -q "@root_validator" modules/payments/config/payment_config.py; then
    # Add model_validator import if not present
    if ! grep -q "model_validator" modules/payments/config/payment_config.py; then
        sed -i.bak '/from pydantic import/ s/$/\, model_validator/' modules/payments/config/payment_config.py
        sed -i.bak 's/,\s*,/,/g' modules/payments/config/payment_config.py
    fi
    # Replace root_validator with model_validator
    sed -i.bak 's/@root_validator/@model_validator(mode='"'"'after'"'"')/g' modules/payments/config/payment_config.py
    # Fix the method signature
    sed -i.bak '/@model_validator/,/return/ {
        s/def \([^(]*\)(cls, values)/def \1(self)/
        s/values\.get(/self./g
        s/values\[/self./g
        s/return values/return self/
    }' modules/payments/config/payment_config.py
fi

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ Root validator fixes applied!"