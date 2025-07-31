#!/bin/bash
# Build documentation locally for testing

echo "Building MkDocs documentation..."

# Install dependencies if needed
pip install -r requirements.txt

# Build the documentation
python -m mkdocs build --verbose

echo "Documentation built successfully!"
echo "To serve locally, run: python -m mkdocs serve"
echo "To deploy to Netlify, push to the repository"