.PHONY: install install-dev test lint format clean run-dry help

PYTHON  ?= python
PYTEST  ?= pytest
PIP     ?= pip

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Install NullShift (production dependencies)
	$(PIP) install -e .

install-dev:  ## Install NullShift with all development dependencies
	$(PIP) install -e ".[all]"
	$(PIP) install pytest pytest-mock pytest-cov black isort autoflake

test:  ## Run the full test suite
	$(PYTEST) tests/ -v

test-cov:  ## Run tests with coverage report
	$(PYTEST) tests/ -v --cov=patchwork --cov-report=term-missing --cov-report=html

lint:  ## Check code style (no changes)
	black --check patchwork/ tests/
	isort --check-only patchwork/ tests/

format:  ## Auto-format code with black + isort
	autoflake --recursive --in-place patchwork/ tests/
	isort patchwork/ tests/
	black patchwork/ tests/

clean:  ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

run-dry:  ## Demo dry-run against the current repo diff (requires GROQ_API_KEY)
	@echo "Running NullShift in dry-run mode against current branch diff..."
	nullshift NullShift \
		openai_api_key=$(GROQ_API_KEY) \
		pr_diff="$$(git diff origin/main)" \
		dry_run
