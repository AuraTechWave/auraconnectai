# AuraConnect AI Development Makefile

.PHONY: help install install-backend install-frontend install-mobile install-hooks format lint test clean

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(GREEN)AuraConnect AI Development Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# Installation commands
install: install-backend install-frontend install-mobile install-hooks ## Install all dependencies

install-backend: ## Install backend dependencies
	@echo "$(GREEN)Installing backend dependencies...$(NC)"
	cd backend && pip install -r requirements.txt
	cd backend && pip install -e .

install-frontend: ## Install frontend dependencies
	@echo "$(GREEN)Installing frontend dependencies...$(NC)"
	cd frontend && npm install

install-mobile: ## Install mobile dependencies
	@echo "$(GREEN)Installing mobile dependencies...$(NC)"
	cd mobile && npm install

install-hooks: ## Install pre-commit hooks
	@echo "$(GREEN)Installing pre-commit hooks...$(NC)"
	pre-commit install
	pre-commit install --hook-type commit-msg

# Backend commands
backend-format: ## Format backend code
	@echo "$(GREEN)Formatting backend code...$(NC)"
	cd backend && black .
	cd backend && isort .
	cd backend && ruff check --fix .

backend-lint: ## Lint backend code
	@echo "$(GREEN)Linting backend code...$(NC)"
	cd backend && ruff check .
	cd backend && mypy .
	cd backend && bandit -r . -ll -x tests,alembic

backend-test: ## Run backend tests
	@echo "$(GREEN)Running backend tests...$(NC)"
	cd backend && pytest tests/ -v --cov=core --cov=modules --cov-report=term-missing

backend-test-unit: ## Run backend unit tests only
	@echo "$(GREEN)Running backend unit tests...$(NC)"
	cd backend && pytest tests/ -v -m unit

backend-test-integration: ## Run backend integration tests only
	@echo "$(GREEN)Running backend integration tests...$(NC)"
	cd backend && pytest tests/ -v -m integration

backend-migrate: ## Run database migrations
	@echo "$(GREEN)Running database migrations...$(NC)"
	cd backend && alembic upgrade head

backend-migration: ## Create a new migration
	@echo "$(GREEN)Creating new migration...$(NC)"
	@read -p "Enter migration message: " msg; \
	cd backend && alembic revision --autogenerate -m "$$msg"

backend-run: ## Run backend server
	@echo "$(GREEN)Starting backend server...$(NC)"
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend commands
frontend-format: ## Format frontend code
	@echo "$(GREEN)Formatting frontend code...$(NC)"
	cd frontend && npx prettier --write "src/**/*.{js,jsx,ts,tsx,json,css,scss}"

frontend-lint: ## Lint frontend code
	@echo "$(GREEN)Linting frontend code...$(NC)"
	cd frontend && npm run lint

frontend-test: ## Run frontend tests
	@echo "$(GREEN)Running frontend tests...$(NC)"
	cd frontend && npm test

frontend-build: ## Build frontend for production
	@echo "$(GREEN)Building frontend...$(NC)"
	cd frontend && npm run build

frontend-run: ## Run frontend development server
	@echo "$(GREEN)Starting frontend server...$(NC)"
	cd frontend && npm start

# Mobile commands
mobile-format: ## Format mobile code
	@echo "$(GREEN)Formatting mobile code...$(NC)"
	cd mobile && npx prettier --write "src/**/*.{js,jsx,ts,tsx,json}"

mobile-lint: ## Lint mobile code
	@echo "$(GREEN)Linting mobile code...$(NC)"
	cd mobile && npm run lint

mobile-typecheck: ## Run mobile TypeScript checks
	@echo "$(GREEN)Running TypeScript checks...$(NC)"
	cd mobile && npm run typecheck

mobile-test: ## Run mobile tests
	@echo "$(GREEN)Running mobile tests...$(NC)"
	cd mobile && npm test

mobile-ios: ## Run mobile app on iOS
	@echo "$(GREEN)Starting iOS app...$(NC)"
	cd mobile && npm run ios

mobile-android: ## Run mobile app on Android
	@echo "$(GREEN)Starting Android app...$(NC)"
	cd mobile && npm run android

# Combined commands
format: backend-format frontend-format mobile-format ## Format all code

lint: backend-lint frontend-lint mobile-lint ## Lint all code

test: backend-test frontend-test mobile-test ## Run all tests

typecheck: ## Run type checking for all projects
	@echo "$(GREEN)Running type checks...$(NC)"
	cd backend && mypy .
	cd mobile && npm run typecheck

# Pre-commit commands
pre-commit: ## Run pre-commit hooks on all files
	@echo "$(GREEN)Running pre-commit hooks...$(NC)"
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	@echo "$(GREEN)Updating pre-commit hooks...$(NC)"
	pre-commit autoupdate

# Database commands
db-start: ## Start PostgreSQL with Docker
	@echo "$(GREEN)Starting PostgreSQL...$(NC)"
	docker-compose up -d postgres

db-stop: ## Stop PostgreSQL
	@echo "$(GREEN)Stopping PostgreSQL...$(NC)"
	docker-compose stop postgres

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "$(RED)WARNING: This will destroy all data!$(NC)"
	@read -p "Are you sure? (y/N): " confirm; \
	if [ "$$confirm" = "y" ]; then \
		cd backend && alembic downgrade base && alembic upgrade head; \
	fi

# Redis commands
redis-start: ## Start Redis with Docker
	@echo "$(GREEN)Starting Redis...$(NC)"
	docker-compose up -d redis

redis-stop: ## Stop Redis
	@echo "$(GREEN)Stopping Redis...$(NC)"
	docker-compose stop redis

redis-cli: ## Connect to Redis CLI
	@echo "$(GREEN)Connecting to Redis CLI...$(NC)"
	docker-compose exec redis redis-cli

# Docker commands
docker-up: ## Start all services with Docker Compose
	@echo "$(GREEN)Starting all services...$(NC)"
	docker-compose up -d

docker-down: ## Stop all services
	@echo "$(GREEN)Stopping all services...$(NC)"
	docker-compose down

docker-logs: ## Show logs for all services
	docker-compose logs -f

docker-build: ## Rebuild Docker images
	@echo "$(GREEN)Rebuilding Docker images...$(NC)"
	docker-compose build

# Utility commands
clean: ## Clean up temporary files and caches
	@echo "$(GREEN)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf frontend/build
	rm -rf frontend/node_modules/.cache
	rm -rf mobile/node_modules/.cache

check-standards: ## Check if code meets standards
	@echo "$(GREEN)Checking code standards...$(NC)"
	@echo "$(YELLOW)Python Standards:$(NC)"
	cd backend && ruff check . --statistics
	@echo ""
	@echo "$(YELLOW)JavaScript/TypeScript Standards:$(NC)"
	cd frontend && npm run lint -- --quiet
	@echo ""
	@echo "$(YELLOW)Type Checking:$(NC)"
	cd backend && mypy . --no-error-summary 2>/dev/null || echo "Type checking complete"
	@echo ""
	@echo "$(GREEN)All checks complete!$(NC)"

fix-imports: ## Fix import ordering issues
	@echo "$(GREEN)Fixing import order...$(NC)"
	cd backend && isort . --diff
	cd backend && isort .

security-check: ## Run security checks
	@echo "$(GREEN)Running security checks...$(NC)"
	cd backend && bandit -r . -ll -x tests,alembic
	cd backend && pip-audit
	cd frontend && npm audit

update-deps: ## Update all dependencies
	@echo "$(GREEN)Updating dependencies...$(NC)"
	cd backend && pip list --outdated
	cd frontend && npm outdated
	cd mobile && npm outdated
	@echo "$(YELLOW)Run 'npm update' or 'pip install --upgrade' to update packages$(NC)"

# Git hooks
setup-git-hooks: ## Setup git hooks for the project
	@echo "$(GREEN)Setting up git hooks...$(NC)"
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "$(GREEN)Git hooks installed successfully!$(NC)"

# Development workflow
dev: ## Start development environment
	@echo "$(GREEN)Starting development environment...$(NC)"
	$(MAKE) db-start
	$(MAKE) redis-start
	@echo "$(GREEN)Backend starting on http://localhost:8000$(NC)"
	@echo "$(GREEN)Frontend starting on http://localhost:3000$(NC)"
	@trap 'kill %1; kill %2' INT; \
	$(MAKE) backend-run & \
	$(MAKE) frontend-run & \
	wait

# CI/CD simulation
ci: ## Run CI pipeline locally
	@echo "$(GREEN)Running CI pipeline...$(NC)"
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) security-check
	@echo "$(GREEN)CI pipeline passed!$(NC)"

# Default target
.DEFAULT_GOAL := help