"""
端到端集成测试
"""

import pytest
from pydantic_resolve import config_global_resolver, query
from pydantic_resolve.graphql import GraphQLHandler
from pydantic import BaseModel
from typing import List, Optional


class TestGraphQLIntegration:
    """端到端集成测试"""

    def setup_method(self):
        """设置测试环境"""

        # 创建简单的 ERD（只用于测试）
        from pydantic_resolve import base_entity
        TestBase = base_entity()

        class SimpleEntity(BaseModel, TestBase):
            __relationships__ = []
            id: int
            name: str

            @query
            async def get_all(cls, limit: int = 10) -> List['SimpleEntity']:
                """获取所有简单实体"""
                return [
                    SimpleEntity(id=1, name='Alice'),
                    SimpleEntity(id=2, name='Bob'),
                ][:limit]

        self.er_diagram = TestBase.get_diagram()
        config_global_resolver(self.er_diagram)
        self.handler = GraphQLHandler(self.er_diagram)

    @pytest.mark.asyncio
    async def test_simple_query_execution(self):
        """测试简单查询执行"""
        query_str = "{ simpleEntityGetAll { id name } }"
        result = await self.handler.execute(query_str)

        # 验证响应格式
        assert "data" in result
        assert "errors" in result

        # 验证没有错误
        assert result["errors"] is None or len(result["errors"]) == 0

        # 验证数据
        assert "simpleEntityGetAll" in result["data"]
        users = result["data"]["simpleEntityGetAll"]
        assert len(users) <= 2

    @pytest.mark.asyncio
    async def test_query_with_arguments(self):
        """测试带参数的查询"""
        query_str = "{ simpleEntityGetAll(limit: 1) { id } }"
        result = await self.handler.execute(query_str)

        # 验证响应
        assert "data" in result
        assert "simpleEntityGetAll" in result["data"]
        assert len(result["data"]["simpleEntityGetAll"]) == 1

    @pytest.mark.asyncio
    async def test_invalid_query(self):
        """测试无效查询"""
        query_str = "{ non_existent { id } }"
        result = await self.handler.execute(query_str)

        # 验证错误响应
        assert "errors" in result
        assert result["errors"] is not None
        assert len(result["errors"]) > 0

    def test_graphql_handler_integration(self):
        """测试 GraphQLHandler 集成"""
        try:
            from fastapi import APIRouter
        except ImportError:
            pytest.skip("FastAPI not available")

        # 定义请求模型
        class GraphQLRequest(BaseModel):
            query: str
            operationName: Optional[str] = None

        # 创建路由
        router = APIRouter()

        @router.post("/test")
        async def graphql_endpoint(req: GraphQLRequest):
            result = await self.handler.execute(
                query=req.query,
            )
            return result

        # 验证路由创建
        assert router is not None
        assert len(router.routes) >= 1

        # 测试查询
        assert self.handler is not None
        assert hasattr(self.handler, 'execute')

    def test_create_graphql_route_removed(self):
        """确认 create_graphql_route 已被移除"""
        with pytest.raises(ImportError):
            from pydantic_resolve.graphql import create_graphql_route  # noqa: F401

        with pytest.raises(ImportError):
            from pydantic_resolve import create_graphql_route  # noqa: F401

