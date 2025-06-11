#!/bin/bash

echo "🚀 Generating Alembic Migration for Staff Module..."
alembic revision --autogenerate -m "Create staff tables"
sleep 1
echo "✅ Reviewing new migration file..."
ls -lt alembic/versions | head -n 1
sleep 1
echo "⚙️ Applying migration..."
alembic upgrade head
echo "✅ All staff module tables are now created!"
echo "🚀 Generating Alembic Migration for User Module..."