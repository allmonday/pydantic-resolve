.PHONY: test test-dfs test-bfs lint

test:
	uv run pytest tests/ -q
	uv run pytest tests/ -q --bfs-compat

test-dfs:
	uv run pytest tests/ -q

test-bfs:
	uv run pytest tests/ -q --bfs-compat

lint:
	uv run ruff check --fix .
