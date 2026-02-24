.PHONY: help run test test-curl clean

# 默认目标
help:
	@echo "GraphQL Demo - 可用命令:"
	@echo ""
	@echo "  make run        - 启动 GraphQL 服务器"
	@echo "  make test       - 运行 Python 测试脚本"
	@echo "  make test-curl  - 运行 Curl 查询测试（需要服务器先启动）"
	@echo "  make clean      - 清理 Python 缓存文件"
	@echo ""
	@echo "示例查询:"
	@echo "  curl -X POST http://localhost:8000/graphql -H 'Content-Type: application/json' -d '{\"query\": \"{ users { id name } }\"}'"

# 启动服务器
run:
	@echo "Starting GraphQL Demo Server..."
	@echo "Server running at http://localhost:8000"
	@echo "Press Ctrl+C to stop"
	@echo ""
	uv run uvicorn demo.graphql.app:app --reload

# 运行 Python 测试
test:
	@echo "Running Python tests..."
	uv run python demo/graphql/test_demo.py

# 运行 Curl 测试（需要服务器先启动）
test-curl:
	@echo "Running curl query tests..."
	@echo "Make sure server is running first (make run)"
	@echo ""
	./demo/graphql/test_queries.sh

# 清理缓存
clean:
	@echo "Cleaning Python cache files..."
	find demo -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find demo -type f -name "*.pyc" -delete 2>/dev/null || true
	find demo -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Done!"
