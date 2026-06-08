.PHONY: test lint

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check --fix .
