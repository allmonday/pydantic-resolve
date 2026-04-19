"""
Tests for GraphQL limit/offset pagination on one-to-many relationships.

Covers:
- SDL generation: Pagination/Result types for unified field strategy
- ResponseBuilder: Result model construction with limit/offset args
- End-to-end query execution with limit/offset/total_count
- Per-parent pagination correctness
"""

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, Integer, String, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pydantic_resolve import Entity, ErDiagram, QueryConfig, Relationship, config_global_resolver
from pydantic_resolve.graphql import GraphQLHandler
from pydantic_resolve.integration.mapping import Mapping
from pydantic_resolve.integration.sqlalchemy import build_relationship


# =====================================
# ORM Models
# =====================================


class Base(DeclarativeBase):
    pass


class AuthorOrm(Base):
    __tablename__ = "author"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # order_by is mandatory for pagination
    articles: Mapped[list["ArticleOrm"]] = relationship(
        back_populates="author",
        order_by="ArticleOrm.id"
    )


class ArticleOrm(Base):
    __tablename__ = "article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author: Mapped["AuthorOrm"] = relationship(back_populates="articles")


# =====================================
# Pydantic DTOs
# =====================================


class AuthorEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ArticleEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author_id: int


# =====================================
# Fixtures
# =====================================


@pytest.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed data: 3 authors, 7 articles
    # Author 1: 3 articles, Author 2: 2 articles, Author 3: 2 articles
    async with async_session() as session:
        async with session.begin():
            session.add_all(
                [
                    AuthorOrm(id=1, name="Alice"),
                    AuthorOrm(id=2, name="Bob"),
                    AuthorOrm(id=3, name="Charlie"),
                ]
            )
            session.add_all(
                [
                    ArticleOrm(id=1, title="A1", author_id=1),
                    ArticleOrm(id=2, title="A2", author_id=1),
                    ArticleOrm(id=3, title="A3", author_id=1),
                    ArticleOrm(id=4, title="B1", author_id=2),
                    ArticleOrm(id=5, title="B2", author_id=2),
                    ArticleOrm(id=6, title="C1", author_id=3),
                    ArticleOrm(id=7, title="C2", author_id=3),
                ]
            )

    try:
        yield async_session
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(session_maker):
    def _factory():
        return session_maker()

    return _factory


@pytest.fixture
def diagram(session_factory):
    async def get_all_authors() -> list[AuthorEntity]:
        async with session_factory() as session:
            rows = (await session.execute(select(AuthorOrm).order_by(AuthorOrm.id))).scalars().all()
        return [AuthorEntity.model_validate(r) for r in rows]

    relationship_entities = build_relationship(
        mappings=[
            Mapping(entity=AuthorEntity, orm=AuthorOrm),
            Mapping(entity=ArticleEntity, orm=ArticleOrm),
        ],
        session_factory=session_factory,
    )

    qm_entities = [
        Entity(
            kls=AuthorEntity,
            queries=[
                QueryConfig(method=get_all_authors, name="authors", description="Get all authors"),
            ],
        ),
    ]

    d = ErDiagram(entities=qm_entities).add_relationship(relationship_entities)
    config_global_resolver(d)
    return d


# =====================================
# Test: SDL Generation
# =====================================


class TestSDLPagination:
    """Test that SDL generation includes Pagination/Result types when enable_pagination=True."""

    def test_pagination_types_in_sdl(self, diagram):
        """Verify Pagination and ArticleEntityResult types exist in SDL when pagination enabled."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        sdl = handler.schema_builder.build_schema()

        # Pagination type should appear once
        assert "type Pagination" in sdl
        assert "has_more: Boolean!" in sdl
        assert "total_count: Int" in sdl

        # ArticleEntityResult type
        assert "type ArticleEntityResult" in sdl
        assert "items: [ArticleEntity!]!" in sdl
        assert "pagination: Pagination!" in sdl

    def test_paginated_field_in_sdl(self, diagram):
        """Verify list field becomes paginated with limit/offset args when pagination enabled."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        sdl = handler.schema_builder.build_schema()

        # Paginated field (with limit/offset args)
        assert "articles(limit: Int, offset: Int): ArticleEntityResult!" in sdl

        # Raw list field should NOT exist when pagination is enabled
        assert "articles: [ArticleEntity!]!" not in sdl

    def test_raw_list_when_pagination_disabled(self, diagram):
        """Verify raw list field when pagination is disabled."""
        handler = GraphQLHandler(diagram, enable_from_attribute_in_type_adapter=True)
        sdl = handler.schema_builder.build_schema()

        # Raw list field (no pagination args)
        assert "articles: [ArticleEntity!]!" in sdl

        # No Pagination/Result types
        assert "type Pagination" not in sdl
        assert "type ArticleEntityResult" not in sdl

    def test_many_to_one_field_has_no_pagination(self, diagram):
        """Verify ArticleEntity's author field is unchanged (many-to-one)."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        sdl = handler.schema_builder.build_schema()

        # ArticleEntity's author field should NOT have pagination args
        # (it's many-to-one, not one-to-many)
        assert "author: AuthorEntity" in sdl


# =====================================
# Test: End-to-End Query Execution
# =====================================


class TestPaginationQueryExecution:
    """Test end-to-end pagination query execution with limit/offset."""

    @pytest.mark.asyncio
    async def test_default_page_size(self, diagram):
        """Query with no limit/offset should use default page_size=20."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id name articles { items { title } pagination { has_more } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]
        assert len(authors) == 3

        # Default page_size=20, so all articles should be returned
        alice = authors[0]
        assert alice["name"] == "Alice"
        assert len(alice["articles"]["items"]) == 3
        assert alice["articles"]["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_limit_results(self, diagram):
        """Query with limit should restrict results per parent."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id name articles(limit: 2) { items { title } pagination { has_more } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]

        # Alice has 3 articles, limit=2 should return 2 and has_more=true
        alice = authors[0]
        assert alice["name"] == "Alice"
        assert len(alice["articles"]["items"]) == 2
        assert alice["articles"]["pagination"]["has_more"] is True

        # Bob has 2 articles, limit=2 should return 2 and has_more=false
        bob = authors[1]
        assert bob["name"] == "Bob"
        assert len(bob["articles"]["items"]) == 2
        assert bob["articles"]["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_offset_pagination(self, diagram):
        """Test offset-based pagination."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        # Page 1: limit=1, offset=0 for Alice
        result = await handler.execute(
            "{ authorEntityAuthors { id name articles(limit: 1, offset: 0) { items { title } pagination { has_more } } } }"
        )

        assert result["errors"] is None
        alice = result["data"]["authorEntityAuthors"][0]
        assert len(alice["articles"]["items"]) == 1
        assert alice["articles"]["items"][0]["title"] == "A1"
        assert alice["articles"]["pagination"]["has_more"] is True

        # Page 2: limit=10, offset=1 for Alice
        result2 = await handler.execute(
            "{ authorEntityAuthors { id name articles(limit: 10, offset: 1) { items { title } pagination { has_more } } } }"
        )

        assert result2["errors"] is None
        alice2 = result2["data"]["authorEntityAuthors"][0]
        assert len(alice2["articles"]["items"]) == 2
        assert alice2["articles"]["items"][0]["title"] == "A2"
        assert alice2["articles"]["items"][1]["title"] == "A3"
        assert alice2["articles"]["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_total_count(self, diagram):
        """Query with total_count should return accurate counts."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id articles(limit: 1) { items { title } pagination { has_more total_count } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]

        # Alice: 3 total
        assert authors[0]["articles"]["pagination"]["total_count"] == 3
        assert len(authors[0]["articles"]["items"]) == 1

        # Bob: 2 total
        assert authors[1]["articles"]["pagination"]["total_count"] == 2

        # Charlie: 2 total
        assert authors[2]["articles"]["pagination"]["total_count"] == 2

    @pytest.mark.asyncio
    async def test_per_parent_isolation(self, diagram):
        """Each parent should only see their own children."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id name articles(limit: 10) { items { title author_id } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]

        for author in authors:
            for item in author["articles"]["items"]:
                assert item["author_id"] == author["id"]

    @pytest.mark.asyncio
    async def test_raw_list_when_pagination_disabled(self, diagram):
        """Query raw list field when pagination is disabled should return all items."""
        handler = GraphQLHandler(diagram, enable_from_attribute_in_type_adapter=True)

        result = await handler.execute(
            "{ authorEntityAuthors { id name articles { title } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]

        # Alice should have all 3 articles
        alice = authors[0]
        assert alice["name"] == "Alice"
        assert len(alice["articles"]) == 3
        assert [a["title"] for a in alice["articles"]] == ["A1", "A2", "A3"]

    @pytest.mark.asyncio
    async def test_pagination_field_excluded_when_not_selected(self, diagram):
        """When pagination is not selected, it should not appear in the response."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id articles(limit: 10) { items { title } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]
        alice = authors[0]

        # pagination key should not be present
        assert "pagination" not in alice["articles"]
        # items should still be present
        assert len(alice["articles"]["items"]) == 3

    @pytest.mark.asyncio
    async def test_total_count_excluded_when_not_selected(self, diagram):
        """When total_count is not selected, only has_more should appear in pagination."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id articles(limit: 2) { items { title } pagination { has_more } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]
        alice = authors[0]

        pag = alice["articles"]["pagination"]
        assert "has_more" in pag
        assert pag["has_more"] is True
        assert "total_count" not in pag

    @pytest.mark.asyncio
    async def test_has_more_excluded_when_not_selected(self, diagram):
        """When has_more is not selected, only total_count should appear in pagination."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id articles(limit: 2) { items { title } pagination { total_count } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]
        alice = authors[0]

        pag = alice["articles"]["pagination"]
        assert "total_count" in pag
        assert pag["total_count"] == 3
        assert "has_more" not in pag


# =====================================
# Test: Introspection with Pagination
# =====================================


def _find_type_by_name(types, name):
    return next((t for t in types if t["name"] == name), None)


def _find_field_by_name(fields, name):
    return next((f for f in fields if f["name"] == name), None)


class TestIntrospectionPagination:
    """Test that introspection includes Pagination/Result types for limit/offset pagination."""

    def test_pagination_type_exists(self, diagram):
        """Verify Pagination type in introspection when pagination enabled."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        schema = handler.introspection._generator.generate()
        pagination = _find_type_by_name(schema["types"], "Pagination")

        assert pagination is not None
        assert pagination["kind"] == "OBJECT"
        field_names = {f["name"] for f in pagination["fields"]}
        assert field_names == {"has_more", "total_count"}

    def test_result_type_exists(self, diagram):
        """Verify ArticleEntityResult type in introspection when pagination enabled."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        schema = handler.introspection._generator.generate()
        result = _find_type_by_name(schema["types"], "ArticleEntityResult")

        assert result is not None
        assert result["kind"] == "OBJECT"
        field_names = {f["name"] for f in result["fields"]}
        assert field_names == {"items", "pagination"}

        # items: [ArticleEntity!]!
        items_field = _find_field_by_name(result["fields"], "items")
        assert items_field["type"]["kind"] == "NON_NULL"
        assert items_field["type"]["ofType"]["kind"] == "LIST"
        assert items_field["type"]["ofType"]["ofType"]["kind"] == "NON_NULL"
        assert items_field["type"]["ofType"]["ofType"]["ofType"]["kind"] == "OBJECT"
        assert items_field["type"]["ofType"]["ofType"]["ofType"]["name"] == "ArticleEntity"

        # pagination: Pagination!
        pagination_field = _find_field_by_name(result["fields"], "pagination")
        assert pagination_field["type"]["kind"] == "NON_NULL"
        assert pagination_field["type"]["ofType"]["kind"] == "OBJECT"
        assert pagination_field["type"]["ofType"]["name"] == "Pagination"

    def test_paginated_field_in_introspection(self, diagram):
        """Verify paginated field with limit/offset args in introspection."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        schema = handler.introspection._generator.generate()
        author_type = _find_type_by_name(schema["types"], "AuthorEntity")

        # articles field should be paginated (NOT a raw list)
        articles_field = _find_field_by_name(author_type["fields"], "articles")
        assert articles_field is not None
        # Should have limit and offset arguments
        arg_names = {a["name"] for a in articles_field["args"]}
        assert arg_names == {"limit", "offset"}
        # Type should be NON_NULL -> OBJECT(ArticleEntityResult)
        t = articles_field["type"]
        assert t["kind"] == "NON_NULL"
        assert t["ofType"]["kind"] == "OBJECT"
        assert t["ofType"]["name"] == "ArticleEntityResult"

        # articles_result field should NOT exist
        articles_result_field = _find_field_by_name(author_type["fields"], "articles_result")
        assert articles_result_field is None

    def test_many_to_one_field_unchanged(self, diagram):
        """Verify ArticleEntity's author field has no args and normal type."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        schema = handler.introspection._generator.generate()
        article_type = _find_type_by_name(schema["types"], "ArticleEntity")

        # ArticleEntity's author field (many-to-one) should have no args and normal type
        author_field = _find_field_by_name(article_type["fields"], "author")
        assert author_field is not None
        assert author_field["args"] == []
        # Should be OBJECT type (nullable), not Result
        assert author_field["type"]["kind"] == "OBJECT"
        assert author_field["type"]["name"] == "AuthorEntity"

    def test_introspection_query_by_name(self, diagram):
        """Verify __type(name: ...) works for pagination types."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        # __type(name: "Pagination") should work
        result = handler.introspection._generator._get_introspection_type("Pagination")
        assert result is not None
        assert result["name"] == "Pagination"

        # __type(name: "ArticleEntityResult") should work
        result = handler.introspection._generator._get_introspection_type("ArticleEntityResult")
        assert result is not None
        assert result["name"] == "ArticleEntityResult"


# =====================================
# Test: enable_pagination Validation
# =====================================


class TestPaginationValidation:
    """Test enable_pagination parameter validation."""

    def test_enable_pagination_succeeds_with_order_by(self, diagram):
        """With order_by set on ORM relationships, validation should pass."""
        # AuthorOrm.articles has order_by="ArticleOrm.id", so sort_field is set
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        assert handler is not None

    def test_enable_pagination_fails_without_sort_field(self):
        """Without sort_field on a one-to-many relationship, should raise ValueError."""
        from pydantic_resolve import Entity, ErDiagram

        class SimpleEntity(BaseModel):
            id: int
            name: str

        class ChildEntity(BaseModel):
            id: int
            parent_id: int

        # Build a relationship with sort_field=None (simulates Django/Tortoise)
        async def dummy_loader(keys):
            return [[] for _ in keys]

        rel = Relationship(
            fk="id",
            target=list[ChildEntity],
            name="children",
            loader=dummy_loader,
            sort_field=None,
        )

        diagram = ErDiagram(entities=[
            Entity(
                kls=SimpleEntity,
                queries=[],
                relationships=[rel],
            ),
        ])

        with pytest.raises(ValueError, match="enable_pagination is True"):
            GraphQLHandler(diagram, enable_pagination=True)

    def test_enable_pagination_false_skips_validation(self):
        """With enable_pagination=False (default), no validation runs."""
        from pydantic_resolve import Entity, ErDiagram

        class SimpleEntity(BaseModel):
            id: int
            name: str

        class ChildEntity(BaseModel):
            id: int
            parent_id: int

        async def dummy_loader(keys):
            return [[] for _ in keys]

        rel = Relationship(
            fk="id",
            target=list[ChildEntity],
            name="children",
            loader=dummy_loader,
            sort_field=None,
        )

        diagram = ErDiagram(entities=[
            Entity(
                kls=SimpleEntity,
                queries=[],
                relationships=[rel],
            ),
        ])

        # Should not raise
        handler = GraphQLHandler(diagram)
        assert handler is not None


# =====================================
# Test: Non-unique sort field (Bug 2)
# =====================================


class ItemOrm(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    # Non-unique sort field: many items share the same priority
    priority: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped["CategoryOrm"] = relationship(back_populates="items")


class CategoryOrm(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # order_by on a non-unique column
    items: Mapped[list["ItemOrm"]] = relationship(
        back_populates="category",
        order_by="ItemOrm.priority",
    )


class CategoryEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ItemEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int
    priority: int


@pytest.fixture
async def non_unique_session_maker():
    """Session with items that share duplicate priority values."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed: 2 categories, each with items having duplicate priority values
    # Category 1 (id=1): items with priority [1, 1, 2, 2, 3]
    # Category 2 (id=2): items with priority [1, 1, 1]
    async with async_session() as session:
        async with session.begin():
            session.add_all([
                CategoryOrm(id=1, name="Cat1"),
                CategoryOrm(id=2, name="Cat2"),
            ])
            session.add_all([
                ItemOrm(id=1, name="I1a", category_id=1, priority=1),
                ItemOrm(id=2, name="I1b", category_id=1, priority=1),
                ItemOrm(id=3, name="I2a", category_id=1, priority=2),
                ItemOrm(id=4, name="I2b", category_id=1, priority=2),
                ItemOrm(id=5, name="I3", category_id=1, priority=3),
                ItemOrm(id=6, name="J1a", category_id=2, priority=1),
                ItemOrm(id=7, name="J1b", category_id=2, priority=1),
                ItemOrm(id=8, name="J1c", category_id=2, priority=1),
            ])

    try:
        yield async_session
    finally:
        await engine.dispose()


@pytest.fixture
def non_unique_diagram(non_unique_session_maker):
    def _session_factory():
        return non_unique_session_maker()

    async def get_all_categories() -> list[CategoryEntity]:
        async with _session_factory() as session:
            rows = (await session.execute(select(CategoryOrm).order_by(CategoryOrm.id))).scalars().all()
        return [CategoryEntity.model_validate(r) for r in rows]

    relationship_entities = build_relationship(
        mappings=[
            Mapping(entity=CategoryEntity, orm=CategoryOrm),
            Mapping(entity=ItemEntity, orm=ItemOrm),
        ],
        session_factory=_session_factory,
    )

    qm_entities = [
        Entity(
            kls=CategoryEntity,
            queries=[
                QueryConfig(method=get_all_categories, name="categories", description="Get all categories"),
            ],
        ),
    ]

    d = ErDiagram(entities=qm_entities).add_relationship(relationship_entities)
    config_global_resolver(d)
    return d


class TestNonUniqueSortField:
    """Test pagination works correctly when sort_field has duplicate values (Bug 2)."""

    @pytest.mark.asyncio
    async def test_no_duplicate_rows_with_non_unique_sort(self, non_unique_diagram):
        """Pagination should not produce duplicate rows when sort_field has ties."""
        handler = GraphQLHandler(
            non_unique_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ categoryEntityCategories { id name items(limit: 5) { items { id name } pagination { total_count has_more } } } }"
        )

        assert result["errors"] is None
        categories = result["data"]["categoryEntityCategories"]

        # Category 1: 5 items total, limit=5, all should be returned without duplicates
        cat1 = categories[0]
        assert cat1["name"] == "Cat1"
        items = cat1["items"]["items"]
        item_ids = [i["id"] for i in items]
        # No duplicates
        assert len(item_ids) == len(set(item_ids)), f"Duplicate items found: {item_ids}"
        assert len(items) == 5
        assert cat1["items"]["pagination"]["total_count"] == 5
        assert cat1["items"]["pagination"]["has_more"] is False

        # Category 2: 3 items total, limit=5, all returned
        cat2 = categories[1]
        assert cat2["name"] == "Cat2"
        items2 = cat2["items"]["items"]
        item_ids2 = [i["id"] for i in items2]
        assert len(item_ids2) == len(set(item_ids2)), f"Duplicate items found: {item_ids2}"
        assert len(items2) == 3

    @pytest.mark.asyncio
    async def test_paginated_subset_with_non_unique_sort(self, non_unique_diagram):
        """Pagination with limit smaller than total, with non-unique sort."""
        handler = GraphQLHandler(
            non_unique_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ categoryEntityCategories { id name items(limit: 2) { items { id name priority } pagination { total_count has_more } } } }"
        )

        assert result["errors"] is None
        categories = result["data"]["categoryEntityCategories"]

        # Category 1: 5 items, limit=2, should get 2 items, has_more=True
        cat1 = categories[0]
        assert len(cat1["items"]["items"]) == 2
        assert cat1["items"]["pagination"]["total_count"] == 5
        assert cat1["items"]["pagination"]["has_more"] is True
        # No duplicates
        ids = [i["id"] for i in cat1["items"]["items"]]
        assert len(ids) == len(set(ids))

        # Category 2: 3 items, limit=2, should get 2 items, has_more=True
        cat2 = categories[1]
        assert len(cat2["items"]["items"]) == 2
        assert cat2["items"]["pagination"]["total_count"] == 3
        assert cat2["items"]["pagination"]["has_more"] is True
        ids2 = [i["id"] for i in cat2["items"]["items"]]
        assert len(ids2) == len(set(ids2))


# =====================================
# Test: Nested pagination (Bug 1)
# =====================================

# Reuse existing AuthorOrm but add comments to ArticleOrm


class BlogCommentOrm(Base):
    __tablename__ = "blog_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(String)
    article_id: Mapped[int] = mapped_column(ForeignKey("blog_article.id"))

    article: Mapped["BlogArticleOrm"] = relationship(back_populates="comments")


class BlogArticleOrm(Base):
    __tablename__ = "blog_article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    author_id: Mapped[int] = mapped_column(ForeignKey("blog_author.id"))

    author: Mapped["BlogAuthorOrm"] = relationship(back_populates="articles")
    comments: Mapped[list["BlogCommentOrm"]] = relationship(
        back_populates="article",
        order_by="BlogCommentOrm.id",
    )


class BlogAuthorOrm(Base):
    __tablename__ = "blog_author"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)

    articles: Mapped[list["BlogArticleOrm"]] = relationship(
        back_populates="author",
        order_by="BlogArticleOrm.id",
    )


class BlogAuthorEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class BlogArticleEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author_id: int


class BlogCommentEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    article_id: int


@pytest.fixture
async def nested_session_maker():
    """Session with 3-level nesting: author → articles → comments."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed: 2 authors
    # Author 1: 3 articles (2, 3, 1 comments respectively)
    # Author 2: 1 article (2 comments)
    async with async_session() as session:
        async with session.begin():
            session.add_all([
                BlogAuthorOrm(id=1, name="Alice"),
                BlogAuthorOrm(id=2, name="Bob"),
            ])
            session.add_all([
                BlogArticleOrm(id=1, title="A1", author_id=1),
                BlogArticleOrm(id=2, title="A2", author_id=1),
                BlogArticleOrm(id=3, title="A3", author_id=1),
                BlogArticleOrm(id=4, title="B1", author_id=2),
            ])
            session.add_all([
                BlogCommentOrm(id=1, text="c1", article_id=1),
                BlogCommentOrm(id=2, text="c2", article_id=1),
                BlogCommentOrm(id=3, text="c3", article_id=2),
                BlogCommentOrm(id=4, text="c4", article_id=2),
                BlogCommentOrm(id=5, text="c5", article_id=2),
                BlogCommentOrm(id=6, text="c6", article_id=3),
                BlogCommentOrm(id=7, text="c7", article_id=4),
                BlogCommentOrm(id=8, text="c8", article_id=4),
            ])

    try:
        yield async_session
    finally:
        await engine.dispose()


@pytest.fixture
def nested_diagram(nested_session_maker):
    def _session_factory():
        return nested_session_maker()

    async def get_all_blog_authors() -> list[BlogAuthorEntity]:
        async with _session_factory() as session:
            rows = (await session.execute(
                select(BlogAuthorOrm).order_by(BlogAuthorOrm.id)
            )).scalars().all()
        return [BlogAuthorEntity.model_validate(r) for r in rows]

    relationship_entities = build_relationship(
        mappings=[
            Mapping(entity=BlogAuthorEntity, orm=BlogAuthorOrm),
            Mapping(entity=BlogArticleEntity, orm=BlogArticleOrm),
            Mapping(entity=BlogCommentEntity, orm=BlogCommentOrm),
        ],
        session_factory=_session_factory,
    )

    qm_entities = [
        Entity(
            kls=BlogAuthorEntity,
            queries=[
                QueryConfig(method=get_all_blog_authors, name="blog_authors", description="Get all blog authors"),
            ],
        ),
    ]

    d = ErDiagram(entities=qm_entities).add_relationship(relationship_entities)
    config_global_resolver(d)
    return d


class TestNestedPagination:
    """Test that nested paginated fields receive correct limit/offset (Bug 1)."""

    @pytest.mark.asyncio
    async def test_nested_result_respects_limit(self, nested_diagram):
        """Inner comments(limit:1) should return exactly 1 comment per article."""
        handler = GraphQLHandler(
            nested_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ blogAuthorEntityBlogAuthors { id name articles(limit: 2) { items { id title comments(limit: 1) { items { text } pagination { total_count has_more } } } pagination { total_count has_more } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["blogAuthorEntityBlogAuthors"]
        assert len(authors) == 2

        # Alice: 3 articles, limit=2 → 2 articles, has_more=True
        alice = authors[0]
        assert alice["name"] == "Alice"
        assert len(alice["articles"]["items"]) == 2
        assert alice["articles"]["pagination"]["total_count"] == 3
        assert alice["articles"]["pagination"]["has_more"] is True

        # Each article's comments(limit:1) should return 1 comment
        art1 = alice["articles"]["items"][0]
        assert art1["title"] == "A1"
        assert len(art1["comments"]["items"]) == 1
        assert art1["comments"]["pagination"]["total_count"] == 2
        assert art1["comments"]["pagination"]["has_more"] is True

        art2 = alice["articles"]["items"][1]
        assert art2["title"] == "A2"
        assert len(art2["comments"]["items"]) == 1
        assert art2["comments"]["pagination"]["total_count"] == 3
        assert art2["comments"]["pagination"]["has_more"] is True

        # Bob: 1 article, limit=2 → 1 article, has_more=False
        bob = authors[1]
        assert bob["name"] == "Bob"
        assert len(bob["articles"]["items"]) == 1
        assert bob["articles"]["pagination"]["total_count"] == 1
        assert bob["articles"]["pagination"]["has_more"] is False

        # Bob's article: 2 comments, limit=1 → 1 comment, has_more=True
        bob_art = bob["articles"]["items"][0]
        assert len(bob_art["comments"]["items"]) == 1
        assert bob_art["comments"]["pagination"]["total_count"] == 2
        assert bob_art["comments"]["pagination"]["has_more"] is True

    @pytest.mark.asyncio
    async def test_nested_result_no_limit_returns_all(self, nested_diagram):
        """Without limit, nested field should return all items."""
        handler = GraphQLHandler(
            nested_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ blogAuthorEntityBlogAuthors { id articles(limit: 1) { items { id comments { items { text } pagination { total_count } } } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["blogAuthorEntityBlogAuthors"]

        # Alice: first article has 2 comments (default page_size=20 → all)
        alice_art = authors[0]["articles"]["items"][0]
        assert len(alice_art["comments"]["items"]) == 2
        assert alice_art["comments"]["pagination"]["total_count"] == 2
