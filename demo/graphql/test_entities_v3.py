"""
Tests for entities_v3.py - SQLAlchemy ORM + build_relationship approach

Validates:
1. Query and mutation recognition in GraphQLHandler
2. Query execution via SQLAlchemy async sessions
3. Mutation execution with auto-generated IDs
4. Relationship resolution via build_relationship loaders
5. Input type support
6. ErDiagram configuration
"""

import pytest
from demo.graphql.entities_v3 import (
    diagram_v3,
    UserEntityV3,
    PostEntityV3,
    init_db_v3,
)
from pydantic_resolve.graphql import GraphQLHandler
from pydantic_resolve.graphql.schema_builder import SchemaBuilder
from pydantic_resolve import config_global_resolver


@pytest.fixture
async def handler():
    """Create GraphQLHandler instance with initialized database."""
    await init_db_v3()
    config_global_resolver(diagram_v3)
    return GraphQLHandler(diagram_v3, enable_from_attribute_in_type_adapter=True)


class TestQueryRecognition:
    """Test query recognition in GraphQLHandler."""

    def test_handler_has_query_map(self, handler):
        assert hasattr(handler, "query_map")
        assert len(handler.query_map) > 0

    def test_users_v3_query_exists(self, handler):
        assert "userEntityV3UsersV3" in handler.query_map

    def test_user_v3_query_exists(self, handler):
        assert "userEntityV3UserV3" in handler.query_map

    def test_posts_v3_query_exists(self, handler):
        assert "postEntityV3PostsV3" in handler.query_map

    def test_post_v3_query_exists(self, handler):
        assert "postEntityV3PostV3" in handler.query_map

    def test_comments_v3_query_exists(self, handler):
        assert "commentEntityV3CommentsV3" in handler.query_map


class TestMutationRecognition:
    """Test mutation recognition in GraphQLHandler."""

    def test_handler_has_mutation_map(self, handler):
        assert hasattr(handler, "mutation_map")
        assert len(handler.mutation_map) > 0

    def test_create_user_v3_mutation_exists(self, handler):
        assert "userEntityV3CreateUserV3" in handler.mutation_map

    def test_create_post_v3_mutation_exists(self, handler):
        assert "postEntityV3CreatePostV3" in handler.mutation_map

    def test_create_comment_v3_mutation_exists(self, handler):
        assert "commentEntityV3CreateCommentV3" in handler.mutation_map


class TestQueryExecution:
    """Test query execution."""

    @pytest.mark.asyncio
    async def test_query_users(self, handler):
        result = await handler.execute(
            "{ userEntityV3UsersV3 { id name email role } }"
        )
        assert result["data"] is not None
        users = result["data"]["userEntityV3UsersV3"]
        assert len(users) > 0
        assert users[0]["name"] is not None

    @pytest.mark.asyncio
    async def test_query_user_by_id(self, handler):
        result = await handler.execute(
            "{ userEntityV3UserV3(id: 1) { id name email role } }"
        )
        assert result["data"] is not None
        user = result["data"]["userEntityV3UserV3"]
        assert user["id"] == 1
        assert user["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_query_posts(self, handler):
        result = await handler.execute(
            "{ postEntityV3PostsV3 { id title content status } }"
        )
        assert result["data"] is not None
        assert "postEntityV3PostsV3" in result["data"]
        assert len(result["data"]["postEntityV3PostsV3"]) > 0

    @pytest.mark.asyncio
    async def test_query_posts_with_filter(self, handler):
        result = await handler.execute(
            '{ postEntityV3PostsV3(status: "published") { id title status } }'
        )
        assert result["data"] is not None
        for post in result["data"]["postEntityV3PostsV3"]:
            assert post["status"] == "published"

    @pytest.mark.asyncio
    async def test_query_comments(self, handler):
        result = await handler.execute(
            "{ commentEntityV3CommentsV3 { id text } }"
        )
        assert result["data"] is not None
        assert "commentEntityV3CommentsV3" in result["data"]
        assert len(result["data"]["commentEntityV3CommentsV3"]) > 0


class TestMutationExecution:
    """Test mutation execution."""

    @pytest.mark.asyncio
    async def test_mutation_create_user(self, handler):
        result = await handler.execute(
            'mutation { userEntityV3CreateUserV3(name: "TestUser", email: "test@test.com") { id name email role } }'
        )
        assert result["data"] is not None
        user = result["data"]["userEntityV3CreateUserV3"]
        assert user["name"] == "TestUser"
        assert user["email"] == "test@test.com"
        assert user["role"] == "user"

    @pytest.mark.asyncio
    async def test_mutation_create_user_with_role(self, handler):
        result = await handler.execute(
            'mutation { userEntityV3CreateUserV3(name: "Admin", email: "admin@test.com", role: "admin") { id name role } }'
        )
        assert result["data"] is not None
        assert result["data"]["userEntityV3CreateUserV3"]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_mutation_create_post(self, handler):
        result = await handler.execute(
            'mutation { postEntityV3CreatePostV3(title: "New Post", content: "Content", author_id: 1) { id title content author_id status } }'
        )
        assert result["data"] is not None
        post = result["data"]["postEntityV3CreatePostV3"]
        assert post["title"] == "New Post"
        assert post["author_id"] == 1
        assert post["status"] == "draft"

    @pytest.mark.asyncio
    async def test_mutation_create_comment(self, handler):
        result = await handler.execute(
            'mutation { commentEntityV3CreateCommentV3(text: "Nice article!", author_id: 1, post_id: 1) { id text author_id post_id } }'
        )
        assert result["data"] is not None
        comment = result["data"]["commentEntityV3CreateCommentV3"]
        assert comment["text"] == "Nice article!"
        assert comment["author_id"] == 1
        assert comment["post_id"] == 1


class TestRelationshipResolution:
    """Test relationship resolution via build_relationship loaders."""

    @pytest.mark.asyncio
    async def test_post_author_relationship(self, handler):
        result = await handler.execute(
            "{ postEntityV3PostsV3 { title author { name email } } }"
        )
        assert result["data"] is not None
        posts = result["data"]["postEntityV3PostsV3"]
        assert len(posts) > 0
        for post in posts:
            assert "author" in post
            assert post["author"] is not None
            assert "name" in post["author"]
            assert "email" in post["author"]

    @pytest.mark.asyncio
    async def test_post_comments_relationship(self, handler):
        result = await handler.execute(
            "{ postEntityV3PostsV3 { title comments { text } } }"
        )
        assert result["data"] is not None
        posts = result["data"]["postEntityV3PostsV3"]
        assert len(posts) > 0
        first_post = posts[0]
        if first_post.get("comments"):
            assert len(first_post["comments"]) > 0
            assert "text" in first_post["comments"][0]

    @pytest.mark.asyncio
    async def test_comment_author_relationship(self, handler):
        result = await handler.execute(
            "{ commentEntityV3CommentsV3 { text author { name } } }"
        )
        assert result["data"] is not None
        comments = result["data"]["commentEntityV3CommentsV3"]
        assert len(comments) > 0
        for comment in comments:
            assert "author" in comment
            assert comment["author"] is not None
            assert "name" in comment["author"]

    @pytest.mark.asyncio
    async def test_comment_post_relationship(self, handler):
        result = await handler.execute(
            "{ commentEntityV3CommentsV3 { text post { title } } }"
        )
        assert result["data"] is not None
        comments = result["data"]["commentEntityV3CommentsV3"]
        assert len(comments) > 0
        for comment in comments:
            assert "post" in comment
            assert comment["post"] is not None
            assert "title" in comment["post"]

    @pytest.mark.asyncio
    async def test_user_posts_relationship(self, handler):
        """Test user -> posts relationship (renamed from myposts in v2)."""
        result = await handler.execute(
            "{ userEntityV3UsersV3 { name posts { title status } } }"
        )
        assert result["data"] is not None
        users = result["data"]["userEntityV3UsersV3"]
        assert len(users) > 0
        alice = next((u for u in users if u["name"] == "Alice"), None)
        if alice and alice.get("posts"):
            assert len(alice["posts"]) > 0
            assert "title" in alice["posts"][0]

    @pytest.mark.asyncio
    async def test_user_comments_relationship(self, handler):
        """Test user -> comments relationship (new in v3 via ORM)."""
        result = await handler.execute(
            "{ userEntityV3UsersV3 { name comments { text } } }"
        )
        assert result["data"] is not None
        users = result["data"]["userEntityV3UsersV3"]
        assert len(users) > 0

    @pytest.mark.asyncio
    async def test_nested_relationships(self, handler):
        """Test nested resolution: Post -> Author -> Posts."""
        result = await handler.execute(
            "{ postEntityV3PostsV3(limit: 2) { title author { name email posts { title } } } }"
        )
        assert result["data"] is not None
        posts = result["data"]["postEntityV3PostsV3"]
        assert len(posts) > 0
        for post in posts:
            assert "author" in post
            assert post["author"] is not None
            if post["author"].get("posts"):
                for author_post in post["author"]["posts"]:
                    assert "title" in author_post


class TestInputType:
    """Test Input Type support."""

    @pytest.mark.asyncio
    async def test_create_user_with_input(self, handler):
        result = await handler.execute(
            'mutation { userEntityV3CreateUserWithInputV3(input: {name: "InputUser", email: "input@test.com", role: "user"}) { id name email role } }'
        )
        assert result["data"] is not None
        user = result["data"]["userEntityV3CreateUserWithInputV3"]
        assert user["name"] == "InputUser"
        assert user["email"] == "input@test.com"

    @pytest.mark.asyncio
    async def test_create_post_with_input(self, handler):
        result = await handler.execute(
            'mutation { postEntityV3CreatePostWithInputV3(input: {title: "Input Post", content: "Content", author_id: 1, status: "published"}) { id title content status } }'
        )
        assert result["data"] is not None
        post = result["data"]["postEntityV3CreatePostWithInputV3"]
        assert post["title"] == "Input Post"
        assert post["status"] == "published"


class TestErDiagramConfiguration:
    """Test ErDiagram configuration."""

    def test_diagram_has_configs(self):
        assert len(diagram_v3.entities) == 3

    def test_diagram_contains_user_entity(self):
        entity_names = [cfg.kls.__name__ for cfg in diagram_v3.entities]
        assert "UserEntityV3" in entity_names

    def test_diagram_contains_post_entity(self):
        entity_names = [cfg.kls.__name__ for cfg in diagram_v3.entities]
        assert "PostEntityV3" in entity_names

    def test_diagram_contains_comment_entity(self):
        entity_names = [cfg.kls.__name__ for cfg in diagram_v3.entities]
        assert "CommentEntityV3" in entity_names

    def test_user_entity_has_relationships(self):
        user_cfg = next(
            (cfg for cfg in diagram_v3.entities if cfg.kls == UserEntityV3), None
        )
        assert user_cfg is not None
        assert len(user_cfg.relationships) >= 1
        rel_names = [r.name for r in user_cfg.relationships]
        assert "posts" in rel_names

    def test_post_entity_has_relationships(self):
        post_cfg = next(
            (cfg for cfg in diagram_v3.entities if cfg.kls == PostEntityV3), None
        )
        assert post_cfg is not None
        assert len(post_cfg.relationships) == 2  # author and comments


class TestContextInjection:
    """Test request-context injection into @query methods."""

    @pytest.mark.asyncio
    async def test_context_reaches_query_method(self, handler):
        """Context dict is passed to @query method's context parameter."""
        result = await handler.execute(
            "{ postEntityV3MyPostsV3 { id title author_id } }",
            context={"user_id": 1},
        )
        assert result["errors"] is None
        assert result["data"] is not None
        posts = result["data"]["postEntityV3MyPostsV3"]
        # All posts should belong to user_id=1 (Alice)
        for post in posts:
            assert post["author_id"] == 1

    @pytest.mark.asyncio
    async def test_context_with_different_user(self, handler):
        """Different context values produce different results."""
        result = await handler.execute(
            "{ postEntityV3MyPostsV3 { id title author_id } }",
            context={"user_id": 2},
        )
        assert result["errors"] is None
        assert result["data"] is not None
        posts = result["data"]["postEntityV3MyPostsV3"]
        for post in posts:
            assert post["author_id"] == 2

    @pytest.mark.asyncio
    async def test_context_none_raises_for_required_query(self, handler):
        """Method that requires context raises when context is not provided."""
        result = await handler.execute(
            "{ postEntityV3MyPostsV3 { id title } }",
        )
        # Should have errors because the method raises ValueError
        assert result["errors"] is not None

    @pytest.mark.asyncio
    async def test_query_without_context_unaffected(self, handler):
        """Queries that don't use context still work normally."""
        result = await handler.execute(
            "{ postEntityV3PostsV3 { id title } }",
            context={"user_id": 999},
        )
        assert result["errors"] is None
        assert result["data"] is not None
        # Should return ALL posts, not filtered by user_id
        assert len(result["data"]["postEntityV3PostsV3"]) > 0

    @pytest.mark.asyncio
    async def test_context_hidden_from_schema(self):
        """context parameter should not appear in SDL schema."""
        from demo.graphql.entities_v3 import diagram_v3 as d
        builder = SchemaBuilder(d)
        schema_sdl = builder.build_schema()

        # The MyPostsV3 query should exist but without _context param
        assert "MyPostsV3" in schema_sdl
        # _context should NOT appear as a parameter in the schema
        assert "_context" not in schema_sdl


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
