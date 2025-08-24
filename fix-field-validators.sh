#!/bin/bash

# Fix remaining field_validator issues

echo "🔧 Fixing Field Validator Arguments"
echo "=================================="

cd backend

# Fix all field_validators with pre=True or always=True
echo "Fixing field_validator arguments..."

# Find and fix pre=True
find . -name "*.py" -type f -exec grep -l "@field_validator.*pre=True" {} \; | while read file; do
    echo "  Fixing pre=True in: $file"
    # Replace pre=True with mode='before'
    sed -i.bak 's/@field_validator(\([^)]*\), pre=True/@field_validator(\1, mode='"'"'before'"'"'/g' "$file"
    # Remove always=True if present with mode='before'
    sed -i.bak 's/, mode='"'"'before'"'"', always=True/, mode='"'"'before'"'"'/g' "$file"
    sed -i.bak 's/, always=True, mode='"'"'before'"'"'/, mode='"'"'before'"'"'/g' "$file"
done

# Find and fix always=True (without pre=True)
find . -name "*.py" -type f -exec grep -l "@field_validator.*always=True" {} \; | while read file; do
    echo "  Fixing always=True in: $file"
    # Remove always=True
    sed -i.bak 's/@field_validator(\([^)]*\), always=True)/@field_validator(\1)/g' "$file"
    sed -i.bak 's/, always=True)/)/g' "$file"
done

# Add @classmethod after field_validators that don't have it
echo "Adding @classmethod decorators..."
find . -name "*.py" -type f -exec grep -l "@field_validator" {} \; | while read file; do
    # Check if the next line after @field_validator is not @classmethod
    awk '
    /@field_validator/ {
        validator_line = NR
        validator_text = $0
        getline
        if ($0 !~ /@classmethod/) {
            print "  Adding @classmethod in: " FILENAME " at line " validator_line > "/dev/stderr"
            print validator_text
            print "    @classmethod"
            print $0
        } else {
            print validator_text
            print $0
        }
        next
    }
    { print }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
done

# Clean up backup files
find . -name "*.bak" -type f -delete

echo ""
echo "✅ Field validator fixes applied!"