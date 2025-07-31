#!/bin/bash
#
# Export Mermaid diagrams from documentation to PNG/PDF format
# This script processes all .md files and extracts Mermaid diagrams
#
# Requirements:
# - mermaid-cli (npm install -g @mermaid-js/mermaid-cli)
# - imagemagick (for PDF conversion)
#
# Usage: ./export-diagrams.sh [output_dir]

set -e

# Configuration
DOCS_DIR="${DOCS_DIR:-../../modules/payroll/docs}"
OUTPUT_DIR="${1:-./exported-diagrams}"
TEMP_DIR="/tmp/mermaid-export-$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$TEMP_DIR"

echo -e "${GREEN}Starting diagram export...${NC}"

# Check if mermaid-cli is installed
if ! command -v mmdc &> /dev/null; then
    echo -e "${RED}Error: mermaid-cli is not installed${NC}"
    echo "Please install it with: npm install -g @mermaid-js/mermaid-cli"
    exit 1
fi

# Function to extract mermaid diagrams from a markdown file
extract_diagrams() {
    local md_file="$1"
    local base_name=$(basename "$md_file" .md)
    local rel_path=$(realpath --relative-to="$DOCS_DIR" "$md_file")
    local output_subdir=$(dirname "$rel_path")
    
    # Create output subdirectory
    mkdir -p "$OUTPUT_DIR/$output_subdir"
    
    # Extract mermaid blocks
    local in_mermaid=0
    local diagram_count=0
    local current_diagram=""
    
    while IFS= read -r line; do
        if [[ "$line" =~ ^\`\`\`mermaid ]]; then
            in_mermaid=1
            current_diagram=""
        elif [[ "$line" =~ ^\`\`\` ]] && [ $in_mermaid -eq 1 ]; then
            in_mermaid=0
            diagram_count=$((diagram_count + 1))
            
            # Save diagram to temp file
            local temp_file="$TEMP_DIR/${base_name}_diagram_${diagram_count}.mmd"
            echo "$current_diagram" > "$temp_file"
            
            # Export to PNG
            local output_png="$OUTPUT_DIR/$output_subdir/${base_name}_diagram_${diagram_count}.png"
            echo -e "${YELLOW}  Exporting diagram $diagram_count from $rel_path...${NC}"
            
            mmdc -i "$temp_file" -o "$output_png" -t dark -b white --width 2048 2>/dev/null || {
                echo -e "${RED}  Failed to export diagram $diagram_count from $rel_path${NC}"
            }
            
            # Convert to PDF if imagemagick is available
            if command -v convert &> /dev/null; then
                local output_pdf="${output_png%.png}.pdf"
                convert "$output_png" "$output_pdf" 2>/dev/null || {
                    echo -e "${RED}  Failed to convert diagram to PDF${NC}"
                }
            fi
        elif [ $in_mermaid -eq 1 ]; then
            current_diagram+="$line"$'\n'
        fi
    done < "$md_file"
    
    if [ $diagram_count -gt 0 ]; then
        echo -e "${GREEN}  Exported $diagram_count diagram(s) from $rel_path${NC}"
    fi
    
    return $diagram_count
}

# Process all markdown files
total_files=0
total_diagrams=0

echo -e "${GREEN}Scanning for markdown files in $DOCS_DIR...${NC}"

while IFS= read -r -d '' md_file; do
    echo -e "${YELLOW}Processing: $(basename "$md_file")${NC}"
    extract_diagrams "$md_file"
    diagrams_found=$?
    
    total_files=$((total_files + 1))
    total_diagrams=$((total_diagrams + diagrams_found))
done < <(find "$DOCS_DIR" -name "*.md" -type f -print0)

# Clean up
rm -rf "$TEMP_DIR"

# Create index HTML
cat > "$OUTPUT_DIR/index.html" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Payroll Module Diagrams</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .diagram-section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }
        .diagram-section h2 { color: #666; }
        .diagram { margin: 10px 0; }
        img { max-width: 100%; height: auto; border: 1px solid #eee; }
        .download-links { margin-top: 10px; }
        .download-links a { margin-right: 10px; }
    </style>
</head>
<body>
    <h1>Payroll & Tax Module - Exported Diagrams</h1>
    <p>Generated on: $(date)</p>
    <p>Total diagrams: $total_diagrams from $total_files files</p>
EOF

# Add diagram listings to HTML
for dir in $(find "$OUTPUT_DIR" -type d | sort); do
    if [ "$dir" != "$OUTPUT_DIR" ] && [ -n "$(find "$dir" -name "*.png" 2>/dev/null)" ]; then
        rel_dir=$(realpath --relative-to="$OUTPUT_DIR" "$dir")
        echo "<div class='diagram-section'>" >> "$OUTPUT_DIR/index.html"
        echo "<h2>$rel_dir</h2>" >> "$OUTPUT_DIR/index.html"
        
        for png in "$dir"/*.png; do
            if [ -f "$png" ]; then
                basename=$(basename "$png")
                pdf="${png%.png}.pdf"
                
                echo "<div class='diagram'>" >> "$OUTPUT_DIR/index.html"
                echo "<h3>$basename</h3>" >> "$OUTPUT_DIR/index.html"
                echo "<img src='$rel_dir/$basename' alt='$basename'>" >> "$OUTPUT_DIR/index.html"
                echo "<div class='download-links'>" >> "$OUTPUT_DIR/index.html"
                echo "<a href='$rel_dir/$basename' download>Download PNG</a>" >> "$OUTPUT_DIR/index.html"
                
                if [ -f "$pdf" ]; then
                    echo "<a href='$rel_dir/$(basename "$pdf")' download>Download PDF</a>" >> "$OUTPUT_DIR/index.html"
                fi
                
                echo "</div></div>" >> "$OUTPUT_DIR/index.html"
            fi
        done
        
        echo "</div>" >> "$OUTPUT_DIR/index.html"
    fi
done

echo "</body></html>" >> "$OUTPUT_DIR/index.html"

# Summary
echo -e "${GREEN}Export complete!${NC}"
echo -e "Total files processed: $total_files"
echo -e "Total diagrams exported: $total_diagrams"
echo -e "Output directory: $OUTPUT_DIR"
echo -e "View all diagrams: file://$OUTPUT_DIR/index.html"

# Create README for exported diagrams
cat > "$OUTPUT_DIR/README.md" << EOF
# Exported Payroll Module Diagrams

This directory contains exported diagrams from the Payroll & Tax Module documentation.

## Contents

- PNG images of all Mermaid diagrams
- PDF versions (if ImageMagick is installed)
- index.html for easy viewing

## Generated

- Date: $(date)
- Total diagrams: $total_diagrams
- Source: $DOCS_DIR

## Viewing

Open \`index.html\` in a web browser to view all diagrams with navigation.

## Regenerating

To regenerate these diagrams, run:
\`\`\`bash
./export-diagrams.sh
\`\`\`

## Requirements

- mermaid-cli: \`npm install -g @mermaid-js/mermaid-cli\`
- imagemagick (optional, for PDF conversion): \`apt-get install imagemagick\`
EOF