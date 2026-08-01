#!/bin/bash
# GraphQL Demo 查询测试脚本

BASE_URL="http://localhost:8000/graphql"

echo "=========================================="
echo "GraphQL Demo - 查询测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 测试函数
test_query() {
    local name=$1
    local query=$2

    echo -e "${BLUE}测试: ${name}${NC}"
    echo "查询: $query"
    echo ""
    curl -s -X POST "$BASE_URL" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"$query\"}" | python3 -m json.tool
    echo ""
    echo "------------------------------------------"
    echo ""
}

# 测试 1: 获取所有用户
test_query "获取所有用户" "{ UserEntity { users_v3 { id name email role } } }"

# 测试 2: 获取分页用户
test_query "获取分页用户" "{ UserEntity { users_v3(limit: 2, offset: 1) { id name email } } }"

# 测试 3: 获取单个用户
test_query "获取单个用户" "{ UserEntity { user_v3(id: 1) { id name email role } } }"

# 测试 4: 获取所有文章
test_query "获取所有文章" "{ PostEntity { posts_v3 { id title content status } } }"

# 测试 5: 获取已发布文章
test_query "获取已发布文章" '{ PostEntity { posts_v3(status: "published") { id title } } }'

# 测试 6: 获取单个文章
test_query "获取单个文章" "{ PostEntity { post_v3(id: 1) { id title content } } }"

# 测试 7: 获取评论
test_query "获取评论" "{ CommentEntity { comments_v3 { id text } } }"

# 测试 8: 错误处理 - 未知查询
test_query "错误处理 - 未知查询" "{ NonExistent { id } }"

echo -e "${GREEN}所有测试完成！${NC}"
