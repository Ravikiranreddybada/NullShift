.PHONY: install install-dev test test-cov test-watch lint format clean help run-dry checkdeps

# Python and pip settings
PYTHON  ?= python
PYTEST  ?= pytest
PIP     ?= pip
POETRY  ?= poetry

# Default target
help:  ## Show this help message
	@echo "NullShift - Makefile Commands"
	@echo "=============================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# Installation commands
install:  ## Install NullShift (production dependencies only)
	$(PIP) install -e .

install-dev:  ## Install NullShift with all development dependencies
	$(PIP) install -e ".[all]"
	$(PIP) install pytest pytest-mock pytest-cov black isort autoflake mypy

install-poetry:  ## Install using Poetry
	$(POETRY) install

install-poetry-dev:  ## Install using Poetry with dev dependencies
	$(POETRY) install --all-extras --with dev

# Testing commands
test:  ## Run the full test suite
	$(PYTEST) tests/ -v

test-cov:  ## Run tests with coverage report
	$(PYTEST) tests/ -v --cov=patchwork --cov-report=term-missing --cov-report=html

test-watch:  ## Run tests in watch mode (requires pytest-watch)
	$(PYTEST) tests/ -v --watch

test-unit:  ## Run only unit tests (exclude integration tests)
	$(PYTEST) tests/ -v --ignore=tests/cicd/

test-integration:  ## Run only integration tests
	$(PYTEST) tests/cicd/ -v

test-quick:  ## Run tests without coverage (faster)
	$(PYTEST) tests/ -v --no-cov

# Linting and formatting
lint:  ## Check code style (no changes)
	@echo "Running linting checks..."
	black --check patchwork/ tests/
	isort --check-only patchwork/ tests/
	autoflake --check patchwork/ tests/
	mypy patchwork/ --ignore-missing-imports || true

lint-strict:  ## Strict linting with mypy
	@echo "Running strict linting..."
	black --check patchwork/ tests/
	isort --check-only patchwork/ tests/
	autoflake --check patchwork/ tests/
	mypy patchwork/

format:  ## Auto-format code with black + isort + autoflake
	@echo "Formatting code..."
	autoflake --recursive --in-place patchwork/ tests/
	isort patchwork/ tests/
	black patchwork/ tests/

format-check:  ## Check if code needs formatting (without making changes)
	@echo "Checking formatting..."
	@autoflake --check --recursive patchwork/ tests/ || true
	@isort --check-only patchwork/ tests/ || true
	@black --check patchwork/ tests/ || true

# Code quality
checkdeps:  ## Check for outdated dependencies
	$(PIP) list --outdated || true

security:  ## Run security checks (requires safety)
	@echo "Checking for security vulnerabilities..."
	@pip install safety 2>/dev/null || true
	@safety check || true

# Cleanup commands
clean:  ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage
	rm -rf .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

clean-all:  ## Deep clean (includes virtual environments)
	rm -rf venv/ .venv/
	$(MAKE) clean

# Development commands
run-dry:  ## Demo dry-run against the current repo diff (requires GROQ_API_KEY)
	@echo "Running NullShift in dry-run mode against current branch diff..."
	@if [ -z "$(GROQ_API_KEY)" ]; then \
		echo "Error: GROQ_API_KEY not set. Run with: GROQ_API_KEY=gsk_... make run-dry"; \
		exit 1; \
	fi
	nullshift NullShift \
		groq_api_key=$(GROQ_API_KEY) \
		pr_diff="$$(git diff origin/main)" \
		dry_run

run:  ## Run NullShift with live GitHub PR creation (requires keys)
	@echo "Running NullShift with GitHub PR creation..."
	@if [ -z "$(GROQ_API_KEY)" ] || [ -z "$(GITHUB_API_KEY)" ]; then \
		echo "Error: GROQ_API_KEY and GITHUB_API_KEY not set"; \
		exit 1; \
	fi
	nullshift NullShift \
		groq_api_key=$(GROQ_API_KEY) \
		github_api_key=$(GITHUB_API_KEY) \
		pr_diff="$$(git diff origin/main)"

shell:  ## Open Python shell with NullShift imported
	$(PYTHON) -c "from patchwork.patchflows.NullShift import NullShift; print('NullShift imported successfully!')"

# CI/CD commands (for GitHub Actions)
ci-install:  ## CI: Install dependencies
	$(PIP) install -e ".[all]"
	$(PIP) install pytest pytest-mock pytest-cov

ci-test:  ## CI: Run tests with coverage
	$(PYTEST) tests/ -v --cov=patchwork --cov-report=xml --cov-report=term-missing

ci-lint:  ## CI: Run linting
	black --check patchwork/ tests/
	isort --check-only patchwork/ tests/
	mypy patchwork/ --ignore-missing-imports

# Version and release
version:  ## Show current version
	@$(POETRY) version 2>/dev/null || grep "^version" pyproject.toml | head -1

release:  ## Create a new release (requires poetry)
	@echo "Creating release..."
	$(POETRY) build
	$(POETRY) publish

# Docker commands (optional)
docker-build:  ## Build Docker image
	docker build -t nullshift:latest .

docker-run:  ## Run NullShift in Docker
	docker run -it --rm \
		-e GROQ_API_KEY=$(GROQ_API_KEY) \
		-e GITHUB_API_KEY=$(GITHUB_API_KEY) \
		-v $$(pwd):/app \
		nullshift:latest

# Help text
.DEFAULT_GOAL := help

