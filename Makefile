# Regulatory Monitoring Pipeline - developer task runner.
# Usage: make <target>

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PKG := src/regmon
TESTS := tests

.DEFAULT_GOAL := help

.PHONY: help install hooks lint format test test-cov clean

help: ## Show this help
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install package with dev dependencies
	$(PIP) install -e ".[dev]"

hooks: ## Install pre-commit git hooks
	pre-commit install

lint: ## Run linters and type checker (no changes)
	ruff check $(PKG) $(TESTS)
	black --check $(PKG) $(TESTS)
	mypy $(PKG)

format: ## Auto-format and fix lint issues
	ruff check --fix $(PKG) $(TESTS)
	black $(PKG) $(TESTS)

test: ## Run the test suite
	pytest

test-cov: ## Run tests with coverage report
	pytest --cov=regmon --cov-report=term-missing

clean: ## Remove caches and build artifacts
	$(PYTHON) -c "import shutil,glob,os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) + ['.pytest_cache','.mypy_cache','.ruff_cache','build','dist','htmlcov'] + glob.glob('*.egg-info') + glob.glob('src/*.egg-info')]"
