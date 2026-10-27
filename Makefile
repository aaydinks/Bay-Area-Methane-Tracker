.PHONY: setup lint format test test-all check refresh validate-quick all clean

setup: ## install the locked environment and git hooks
	uv sync --all-extras
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test: ## fast tests (what CI runs)
	uv run pytest -m "not slow and not network"

test-all:
	uv run pytest

check: lint test
	uv run mw config check

refresh: ## pull every source again and rebuild data/interim (safe to repeat)
	uv run mw refresh

validate-quick: ## 20-replicate synthetic coverage check
	uv run mw validate synthetic --quick

# End-to-end rebuild from cached raw pulls. Steps fill in as each phase lands.
all:
	uv run mw sites build
	uv run mw coverage build
	uv run mw validate gate1

clean:
	rm -rf .pytest_cache .ruff_cache .hypothesis htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
