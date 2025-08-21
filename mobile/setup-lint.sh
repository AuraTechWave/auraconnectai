#!/bin/bash

echo "Installing ESLint unused-imports plugin..."
npm install --save-dev eslint-plugin-unused-imports

echo "Running ESLint autofix to clean up unused imports..."
npx eslint . --ext .js,.jsx,.ts,.tsx --fix

echo "ESLint setup complete!"