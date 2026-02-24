#!/bin/bash
# GraphQL Demo 启动脚本

echo "=========================================="
echo "GraphQL Demo Server"
echo "=========================================="
echo ""
echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""
echo "Try these curl commands:"
echo ""
echo "  # Get all users"
echo '  curl -X POST http://localhost:8000/graphql -H "Content-Type: application/json" -d '"'"'{"query": "{ users { id name email role } }"}'"'"
echo ""
echo "  # Get user with posts"
echo '  curl -X POST http://localhost:8000/graphql -H "Content-Type: application/json" -d '"'"'{"query": "{ user(id: 1) { id name email } }"}'"'"
echo ""
echo "  # Get posts with authors"
echo '  curl -X POST http://localhost:8000/graphql -H "Content-Type: application/json" -d '"'"'{"query": "{ posts { title content } }"}'"'"
echo ""
echo "For more examples, see README.md"
echo ""
echo "=========================================="
echo ""

# Use uvicorn for better development experience
uv run uvicorn demo.graphql.app:app --reload
