#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Building backend and frontend Docker images"
docker compose "$@" -f docker-compose.yml build backend frontend

echo "==> Build complete"
