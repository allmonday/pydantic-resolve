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
    query,
)
from pydantic_resolve.graphql import GraphQLHandler, SchemaBuilder
from pydantic_resolve.graphql.schema_errors import (
    DuplicateMethodError,
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
