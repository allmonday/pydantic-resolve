"""
Smoke test for the GraphQL demo.

The demo server (``demo/graphql/app.py``) serves the ``entities_v3`` schema,
so these queries use the grouped layout (``{ Entity { method {} } }``) against
``diagram_v3``. Runs representative queries and asserts they return data with
no errors.
"""

import pytest

from demo.graphql.entities_v3 import diagram_v3, init_db_v3
from pydantic_resolve import config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler


@pytest.fixture
async def handler():
    await init_db_v3()
    config_global_resolver(diagram_v3)
    return GraphQLHandler(diagram_v3, enable_from_attribute_in_type_adapter=True)


@pytest.mark.asyncio
async def test_demo_queries(handler):
    """Representative grouped queries against the v3 demo schema."""
    cases = [
        ("all users", "{ UserEntity { users_v3 { id name email role } } }"),
        ("paginated users", "{ UserEntity { users_v3(limit: 2, offset: 1) { id name email } } }"),
        ("user by id", "{ UserEntity { user_v3(id: 1) { id name email role } } }"),
        ("user with posts", "{ UserEntity { user_v3(id: 1) { id name posts { title status } } } }"),
        ("all posts", "{ PostEntity { posts_v3 { id title content status } } }"),
        ("published posts", '{ PostEntity { posts_v3(status: "published") { id title status } } }'),
        ("post with author", "{ PostEntity { posts_v3 { title author { name email } } } }"),
        ("comments", "{ CommentEntity { comments_v3 { text author { name } post { title } } } }"),
        ("single post", "{ PostEntity { post_v3(id: 1) { title author { name } comments { text } } } }"),
    ]
    for name, query in cases:
        result = await handler.execute(query)
        assert result["errors"] is None, f"{name} failed: {result['errors']}"
        assert result["data"] is not None, f"{name} returned no data"


@pytest.mark.asyncio
async def test_demo_unknown_field_error(handler):
    """An unknown root group returns a clear error."""
    result = await handler.execute("{ NonExistent { id } }")
    assert result["errors"] is not None


if __name__ == "__main__":
    import asyncio
    import json

    async def run():
        await init_db_v3()
        config_global_resolver(diagram_v3)
        h = GraphQLHandler(diagram_v3, enable_from_attribute_in_type_adapter=True)
        for label, query in [
            ("users", "{ UserEntity { users_v3 { id name email role } } }"),
            ("posts", "{ PostEntity { posts_v3 { id title content status } } }"),
        ]:
            print(f"\n== {label} ==")
            print(json.dumps(await h.execute(query), indent=2, ensure_ascii=False))

    asyncio.run(run())
