#!/bin/bash

echo "🚀 AuraConnect Netlify Deployment Starting..."

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "❌ No virtual environment found at .venv/"
    echo "Please run: python3 -m venv .venv && source .venv/bin/activate"
    exit 1
fi

# Install MkDocs dependencies (safe override if needed)
echo "📦 Ensuring mkdocs & material theme are installed..."
pip install mkdocs mkdocs-material --break-system-packages

# Build site
echo "🏗️  Building MkDocs site..."
mkdocs build

# Deploy to Netlify
echo "🌐 Deploying to Netlify..."
netlify deploy --dir=site --prod

# Finish
echo "✅ All done! Check your live site above ☝️"
deactivate
