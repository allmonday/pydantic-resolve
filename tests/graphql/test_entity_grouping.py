"""Tests for the grouped entity GraphQL layout (``{ Entity { method {} } }``).

Covers the migration from the flat ``{Entity}{Method}`` root fields to per-entity
grouping, mirroring nexusx commit 998eb59:
- Schema shape: ``{Entity}Query`` / ``{Entity}Mutation`` group types + root mount fields.
- Execution: two-level dispatch and nested ``data[entity][method]`` response.
- Bare-group and unknown-field friendly errors.
- Eager scan-time conflict detection (DuplicateMethod / Reserved * errors).
"""

from typing import List

import pytest
from pydantic import BaseModel

from pydantic_resolve import (
    Entity,
    ErDiagram,
    QueryConfig,
    base_entity,
    config_global_resolver,
    mutation,
    query,
)
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder
from pydantic_resolve.graphql.mcp.builders.introspection_query_helper import (
    IntrospectionQueryHelper,
)
from pydantic_resolve.graphql.mcp.managers.app_resources import AppResources
from pydantic_resolve.graphql.schema_errors import (
    DuplicateMethodError,
    GroupTypeCollisionError,
    ReservedEntityError,
    ReservedMethodFieldError,
)


# =====================================
# Positive: schema shape + execution
# =====================================


class TestGroupedSchemaShape:
    """The SDL/introspection renders the grouped layout."""

    def test_sdl_has_group_type_and_mount_field(self):
        Base = base_entity()

        class UserEntity(BaseModel, Base):
            __relationships__ = []
            id: int
            name: str

            @query
            async def get_all(cls) -> List["UserEntity"]:
                return []

        diagram = Base.get_diagram()
        sdl = SchemaBuilder(diagram).build_schema()

        # Root Query mounts one NON_NULL field per entity group.
        assert "type Query {" in sdl
        assert "UserEntity: UserEntityQuery!" in sdl
        # The methods live on the {Entity}Query group type, named verbatim.
        assert "type UserEntityQuery {" in sdl
        assert "get_all:" in sdl

    def test_introspection_group_type_present(self):
        Base = base_entity()

        class UserEntity(BaseModel, Base):
            __relationships__ = []
            id: int

            @query
            async def get_all(cls) -> List["UserEntity"]:
                return []

        diagram = Base.get_diagram()
        config_global_resolver(diagram)
        handler = GraphQLHandler(diagram)
        schema = handler.introspection._generator.generate()

        names = {t["name"]: t for t in schema["types"]}
        assert "UserEntityQuery" in names
        group = names["UserEntityQuery"]
        assert group["kind"] == "OBJECT"
        field_names = {f["name"] for f in group["fields"]}
        assert "get_all" in field_names

        # Root Query has the mount field.
        query_type = names["Query"]
        mount_names = {f["name"] for f in query_type["fields"]}
        assert "UserEntity" in mount_names


class TestGroupedExecution:
    """Two-level dispatch nests the response under the entity group."""

    @pytest.mark.asyncio
    async def test_query_data_is_nested_per_entity(self):
        Base = base_entity()

        class UserEntity(BaseModel, Base):
            __relationships__ = []
            id: int
            name: str

            @query
            async def get_all(cls) -> List["UserEntity"]:
                return [UserEntity(id=1, name="Alice")]

        diagram = Base.get_diagram()
        config_global_resolver(diagram)
        handler = GraphQLHandler(diagram)

        result = await handler.execute("{ UserEntity { get_all { id name } } }")

        assert result["errors"] is None
        assert result["data"]["UserEntity"]["get_all"][0]["name"] == "Alice"


# =====================================
# Friendly errors
# =====================================


class TestGroupedErrors:
    """Bare-group and unknown-field errors at execution time."""

    @pytest.mark.asyncio
    async def test_bare_group_returns_bare_group_field_error(self):
        Base = base_entity()

        class UserEntity(BaseModel, Base):
            __relationships__ = []
            id: int

            @query
            async def get_all(cls) -> List["UserEntity"]:
                return []

        diagram = Base.get_diagram()
        config_global_resolver(diagram)
        handler = GraphQLHandler(diagram)

        # `{ User }` (no method subselection) -> BARE_GROUP_FIELD
        result = await handler.execute("{ UserEntity }")

        assert result["errors"] is not None
        err = result["errors"][0]
        assert err["extensions"]["code"] == "BARE_GROUP_FIELD"
        assert err["extensions"]["entity"] == "UserEntity"
        assert "get_all" in err["extensions"]["available_methods"]
        # The example is derived from the method's real signature — get_all has
        # no args, so the example must not fabricate an `(id: 1)` argument.
        assert "(id: 1)" not in err["message"]
        assert "{ UserEntity { get_all { id } } }" in err["message"]

    @pytest.mark.asyncio
    async def test_unknown_entity_group_error(self):
        Base = base_entity()

        class UserEntity(BaseModel, Base):
            __relationships__ = []
            id: int

            @query
            async def get_all(cls) -> List["UserEntity"]:
                return []

        diagram = Base.get_diagram()
        config_global_resolver(diagram)
        handler = GraphQLHandler(diagram)

        result = await handler.execute("{ Missing { anything { id } } }")
        assert result["errors"] is not None
        assert "Cannot query field 'Missing'" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_unknown_method_in_group_error(self):
        Base = base_entity()

        class UserEntity(BaseModel, Base):
            __relationships__ = []
            id: int

            @query
            async def get_all(cls) -> List["UserEntity"]:
                return []

        diagram = Base.get_diagram()
        config_global_resolver(diagram)
        handler = GraphQLHandler(diagram)

        result = await handler.execute("{ UserEntity { no_such_method { id } } }")
        assert result["errors"] is not None
        assert "Cannot query field 'no_such_method'" in result["errors"][0]["message"]
        assert result["errors"][0]["path"] == ["UserEntity", "no_such_method"]


# =====================================
# Eager conflict detection at handler init
# =====================================


class _PlainEntity(BaseModel):
    """Plain entity (no base_entity) for ErDiagram-level conflict tests."""
    id: int


async def _returns_empty() -> List[_PlainEntity]:
    return []


async def _returns_empty_two() -> List[_PlainEntity]:
    return []


class TestEagerConflictDetection:
    """Mirrors nexusx method_scanner conflict checks; fire in GraphQLHandler.__init__."""

    def test_duplicate_method_name_raises(self):
        # Two QueryConfigs on one entity resolving to the same GraphQL field name.
        diagram = ErDiagram(entities=[
            Entity(
                kls=_PlainEntity,
                relationships=[],
                queries=[
                    QueryConfig(method=_returns_empty, name="same"),
                    QueryConfig(method=_returns_empty_two, name="same"),
                ],
            )
        ])
        with pytest.raises(DuplicateMethodError):
            GraphQLHandler(diagram)

    def test_reserved_method_field_raises(self):
        # A method field name starting with `__` collides with GraphQL introspection.
        diagram = ErDiagram(entities=[
            Entity(
                kls=_PlainEntity,
                relationships=[],
                queries=[QueryConfig(method=_returns_empty, name="__hidden")],
            )
        ])
        with pytest.raises(ReservedMethodFieldError):
            GraphQLHandler(diagram)

    def test_reserved_entity_name_raises(self):
        # An entity class named `Query` clashes with the root operation type.
        class Query(BaseModel):  # noqa: A001 - intentionally collides
            id: int

        diagram = ErDiagram(entities=[
            Entity(
                kls=Query,
                relationships=[],
                queries=[QueryConfig(method=_returns_empty, name="all")],
            )
        ])
        with pytest.raises(ReservedEntityError):
            GraphQLHandler(diagram)


# =====================================
# MCP helpers operating on the grouped schema
# =====================================


def _build_grouped_handler():
    """Two entities: UserEntity (query + mutation) and PostEntity (query only)."""
    Base = base_entity()

    class UserEntity(BaseModel, Base):
        __relationships__ = []
        id: int
        name: str

        @query
        async def get_all(cls) -> List["UserEntity"]:
            """Get all users."""
            return []

        @mutation
        async def create(cls, name: str) -> "UserEntity":
            """Create a user."""
            return UserEntity(id=1, name=name)

    class PostEntity(BaseModel, Base):
        __relationships__ = []
        id: int
        title: str

        @query
        async def get_all(cls) -> List["PostEntity"]:
            return []

    diagram = Base.get_diagram()
    config_global_resolver(diagram)
    return GraphQLHandler(diagram)


def _make_helper(handler: GraphQLHandler) -> IntrospectionQueryHelper:
    data = handler.introspection._generator.generate()
    entity_names = {cfg.kls.__name__ for cfg in handler.er_diagram.entities}
    return IntrospectionQueryHelper(data, entity_names)


class TestGroupedMcpHelpers:
    """list_group_operations / get_group_operation against a real grouped schema."""

    def test_list_group_operations_descends_into_groups(self):
        helper = _make_helper(_build_grouped_handler())
        queries = helper.list_group_operations("Query")

        # One entry per method across every entity group; both entities share a
        # method named get_all, so the <entity>.<method> identifiers stay unique.
        names = {q["name"] for q in queries}
        assert names == {"UserEntity.get_all", "PostEntity.get_all"}

        user_get_all = next(q for q in queries if q["name"] == "UserEntity.get_all")
        assert user_get_all["entity"] == "UserEntity"
        assert user_get_all["method"] == "get_all"
        assert user_get_all["description"] and "Get all users" in user_get_all["description"]

    def test_list_group_operations_unknown_type_returns_empty(self):
        helper = _make_helper(_build_grouped_handler())
        assert helper.list_group_operations("Subscription") == []

    def test_get_group_operation_returns_method_field(self):
        helper = _make_helper(_build_grouped_handler())
        field = helper.get_group_operation("Query", "UserEntity", "get_all")
        assert field is not None
        assert field["name"] == "get_all"

        mut_field = helper.get_group_operation("Mutation", "UserEntity", "create")
        assert mut_field is not None
        assert mut_field["name"] == "create"

    def test_get_group_operation_unknown_returns_none(self):
        helper = _make_helper(_build_grouped_handler())
        assert helper.get_group_operation("Query", "UserEntity", "nope") is None
        assert helper.get_group_operation("Query", "Missing", "get_all") is None
        # Cross-group: PostEntity has get_all but no create mutation.
        assert helper.get_group_operation("Mutation", "PostEntity", "create") is None

    def test_unwrap_type_name(self):
        unwrap = IntrospectionQueryHelper._unwrap_type_name
        assert unwrap({"name": "Foo"}) == "Foo"
        assert unwrap(None) is None
        # NON_NULL(OBJECT(Bar))
        assert unwrap({"kind": "NON_NULL", "name": None,
                       "ofType": {"kind": "OBJECT", "name": "Bar", "ofType": None}}) == "Bar"
        # LIST(OBJECT(Baz))
        assert unwrap({"kind": "LIST", "name": None,
                       "ofType": {"kind": "OBJECT", "name": "Baz", "ofType": None}}) == "Baz"

    def test_app_resources_group_and_name_properties(self):
        handler = _build_grouped_handler()
        app = AppResources(
            name="t",
            description="t",
            handler=handler,
            introspection_helper=_make_helper(handler),
            sdl_builder=handler.schema_builder._builder,
        )
        assert app.query_groups == {"UserEntity", "PostEntity"}
        assert app.mutation_groups == {"UserEntity"}
        assert app.query_names == {"UserEntity.get_all", "PostEntity.get_all"}
        assert app.mutation_names == {"UserEntity.create"}


# =====================================
# Edge cases found in the second review pass
# =====================================


class TestGroupedEdgeCases:
    """Hardened edge cases: zero-query schema, group-type collisions,
    description placement, and operation SDL richness."""

    def test_zero_query_schema_omits_empty_query_type(self):
        # A mutation-only app must not emit an invalid empty `type Query {}`,
        # and SDL must agree with introspection (queryType is None).
        Base = base_entity()

        class MutOnly(BaseModel, Base):
            __relationships__ = []
            id: int

            @mutation
            async def create(cls, name: str) -> "MutOnly":
                return MutOnly(id=1)

        diagram = Base.get_diagram()
        sdl = SchemaBuilder(diagram).build_schema()
        assert "type Query {" not in sdl
        assert "type Mutation {" in sdl

        config_global_resolver(diagram)
        intro = GraphQLHandler(diagram).introspection._generator.generate()
        assert intro["queryType"] is None
        assert intro["mutationType"] is not None

    def test_group_type_name_collision_raises(self):
        # Entity `User` produces group type `UserQuery`, colliding with the
        # entity class `UserQuery` — both standalone SDL and the handler reject.
        Base = base_entity()

        class User(BaseModel, Base):
            __relationships__ = []
            id: int

            @query
            async def get_all(cls) -> List["User"]:
                return []

        class UserQuery(BaseModel, Base):  # name intentionally collides with User's group type
            __relationships__ = []
            id: int

            @query
            async def get_all(cls) -> List["UserQuery"]:
                return []

        diagram = Base.get_diagram()
        with pytest.raises(GroupTypeCollisionError):
            SchemaBuilder(diagram).build_schema()

        config_global_resolver(diagram)
        with pytest.raises(GroupTypeCollisionError):
            GraphQLHandler(diagram)

    def test_introspection_description_lives_on_group_type(self):
        # The entity docstring describes the group OBJECT type (matching SDL),
        # not the root mount field.
        Base = base_entity()

        class Widget(BaseModel, Base):
            """A widget entity."""

            __relationships__ = []
            id: int

            @query
            async def get_all(cls) -> List["Widget"]:
                return []

        diagram = Base.get_diagram()
        config_global_resolver(diagram)
        intro = GraphQLHandler(diagram).introspection._generator.generate()
        names = {t["name"]: t for t in intro["types"]}

        assert names["WidgetQuery"]["description"] == "A widget entity."
        mount = next(f for f in names["Query"]["fields"] if f["name"] == "Widget")
        assert mount["description"] is None
