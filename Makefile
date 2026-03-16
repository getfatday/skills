.PHONY: lint lint-fix format test test-cov typecheck release new-cli all

lint:
	uv run ruff check clis/

lint-fix:
	uv run ruff check --fix clis/

format:
	uv run ruff format clis/

test:
	uv run pytest clis/ -q

test-cov:
	uv run pytest clis/ --cov --cov-report=term-missing

typecheck:
	uv run mypy clis/

release:
	@if [ -z "$(CLI)" ]; then \
		echo "Usage: make release CLI=<cli-dir-name>"; \
		exit 1; \
	fi
	@bash scripts/release-cli.sh "clis/$(CLI)"

new-cli:
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make new-cli NAME=<name>"; \
		exit 1; \
	fi
	@bash scripts/new-cli.sh "$(NAME)"

all: lint test
