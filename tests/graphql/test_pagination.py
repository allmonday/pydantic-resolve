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


# =====================================
# Test: Alias rejection
# =====================================


class TestAliasSupport:
    """Test that field aliases are rejected."""

    @pytest.mark.asyncio
    async def test_root_alias_rejected(self, diagram):
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        result = await handler.execute("{ renamed: authorEntityAuthors { id } }")
        assert result["errors"] is not None
        assert "alias" in result["errors"][0]["message"].lower()

    @pytest.mark.asyncio
    async def test_nested_alias_rejected(self, nested_diagram):
        handler = GraphQLHandler(
            nested_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        result = await handler.execute(
            "{ blogAuthorEntityBlogAuthors { n: name articles(limit: 1) { items { t: title } } } }"
        )
        assert result["errors"] is not None
        assert "alias" in result["errors"][0]["message"].lower()


# =====================================
# Test: Pagination through many-to-one (Bug 2 fix)
# =====================================


class TestPaginationThroughManyToOne:
    """Test that pagination params pass through many-to-one relationships."""

    @pytest.mark.asyncio
    async def test_nested_pagination_through_many_to_one(self, nested_diagram):
        """Pagination inside a many-to-one field should work.

        Path: authors -> articles(limit:1) -> items -> author -> articles(limit:1)
        The inner articles(limit:1) should respect the limit.
        """
        handler = GraphQLHandler(
            nested_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            '{ blogAuthorEntityBlogAuthors { id name articles(limit: 1) { items { id title author { id name articles(limit: 1) { items { id title } pagination { total_count has_more } } } } pagination { total_count has_more } } } }'
        )

        assert result["errors"] is None, f"Errors: {result['errors']}"
        authors = result["data"]["blogAuthorEntityBlogAuthors"]

        # Alice: 3 articles, limit=1
        alice = authors[0]
        assert alice["name"] == "Alice"
        assert len(alice["articles"]["items"]) == 1

        # The article's author (Alice again) should have articles(limit:1)
        article = alice["articles"]["items"][0]
        inner_author = article["author"]
        assert inner_author["name"] == "Alice"

        # Inner pagination should also respect limit=1
        inner_articles = inner_author["articles"]["items"]
        assert len(inner_articles) == 1
        assert inner_author["articles"]["pagination"]["total_count"] == 3
        assert inner_author["articles"]["pagination"]["has_more"] is True


# =====================================
# Test: Stable pagination order (Bug 3 fix)
# =====================================


class TestStablePaginationOrder:
    """Test that pagination order is deterministic with non-unique sort fields."""

    @pytest.mark.asyncio
    async def test_pagination_order_is_stable(self, non_unique_diagram):
        """Running the same paginated query twice should return identical results."""
        handler = GraphQLHandler(
            non_unique_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        query = "{ categoryEntityCategories { id name items(limit: 3) { items { id name priority } pagination { total_count } } } }"

        result1 = await handler.execute(query)
        result2 = await handler.execute(query)

        assert result1["errors"] is None
        assert result2["errors"] is None

        categories1 = result1["data"]["categoryEntityCategories"]
        categories2 = result2["data"]["categoryEntityCategories"]

        for cat1, cat2 in zip(categories1, categories2):
            items1 = cat1["items"]["items"]
            items2 = cat2["items"]["items"]
            ids1 = [i["id"] for i in items1]
            ids2 = [i["id"] for i in items2]
            assert ids1 == ids2, f"Order mismatch: {ids1} vs {ids2}"

    @pytest.mark.asyncio
    async def test_pagination_across_pages_no_overlap(self, non_unique_diagram):
        """Items from page 1 and page 2 should not overlap with stable ordering."""
        handler = GraphQLHandler(
            non_unique_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        # Page 1: limit=3
        result1 = await handler.execute(
            "{ categoryEntityCategories { id items(limit: 3) { items { id name priority } } } }"
        )
        # Page 2: offset=3, limit=3
        result2 = await handler.execute(
            "{ categoryEntityCategories { id items(limit: 3, offset: 3) { items { id name priority } } } }"
        )

        assert result1["errors"] is None
        assert result2["errors"] is None

        cats1 = result1["data"]["categoryEntityCategories"]
        cats2 = result2["data"]["categoryEntityCategories"]

        for cat1, cat2 in zip(cats1, cats2):
            ids1 = {i["id"] for i in cat1["items"]["items"]}
            ids2 = {i["id"] for i in cat2["items"]["items"]}
            # No overlap between pages
            assert ids1.isdisjoint(ids2), f"Overlapping items between pages: {ids1 & ids2}"


class TestEmptyPageTotalCount:
    """Regression test: offset exceeding total_count should still report correct total_count."""

    @pytest.mark.asyncio
    async def test_offset_exceeds_total_count(self, diagram):
        """When offset > total_count, items should be empty but total_count must be correct."""
        handler = GraphQLHandler(
            diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ authorEntityAuthors { id name articles(limit: 1, offset: 10) { items { title } pagination { has_more total_count } } } }"
        )

        assert result["errors"] is None
        authors = result["data"]["authorEntityAuthors"]

        # Alice has 3 articles, offset=10 is past all of them
        alice = authors[0]
        assert alice["name"] == "Alice"
        assert alice["articles"]["items"] == []
        assert alice["articles"]["pagination"]["total_count"] == 3
        assert alice["articles"]["pagination"]["has_more"] is False

        # Bob has 2 articles
        bob = authors[1]
        assert bob["articles"]["items"] == []
        assert bob["articles"]["pagination"]["total_count"] == 2
        assert bob["articles"]["pagination"]["has_more"] is False


# =====================================
# Test: Many-to-Many Pagination
# =====================================


# Association table for Student <-> Course M2M
from sqlalchemy import Table, Column, ForeignKey as SAFK, Integer as SAInteger

# Use a separate declarative base to avoid table name conflicts with earlier tests


class M2MBase(DeclarativeBase):
    pass


student_course = Table(
    "student_course",
    M2MBase.metadata,
    Column("student_id", SAInteger, SAFK("m2m_student.id"), primary_key=True),
    Column("course_id", SAInteger, SAFK("m2m_course.id"), primary_key=True),
)


class StudentOrm(M2MBase):
    __tablename__ = "m2m_student"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    courses: Mapped[list["CourseOrm"]] = relationship(
        secondary=student_course,
        back_populates="students",
        order_by="CourseOrm.id",
    )


class CourseOrm(M2MBase):
    __tablename__ = "m2m_course"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    students: Mapped[list["StudentOrm"]] = relationship(
        secondary=student_course,
        back_populates="courses",
        order_by="StudentOrm.id",
    )


class StudentEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CourseEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


@pytest.fixture
async def m2m_session_maker():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(M2MBase.metadata.create_all)

    # Seed:
    # Student 1 (Alice): 4 courses (C1, C2, C3, C4)
    # Student 2 (Bob):   2 courses (C2, C4)
    # Student 3 (Carol): 0 courses
    async with async_session() as session:
        async with session.begin():
            session.add_all(
                [
                    StudentOrm(id=1, name="Alice"),
                    StudentOrm(id=2, name="Bob"),
                    StudentOrm(id=3, name="Carol"),
                ]
            )
            session.add_all(
                [
                    CourseOrm(id=1, title="Math"),
                    CourseOrm(id=2, title="Physics"),
                    CourseOrm(id=3, title="Chemistry"),
                    CourseOrm(id=4, title="Biology"),
                ]
            )
            await session.execute(
                student_course.insert(),
                [
                    {"student_id": 1, "course_id": 1},
                    {"student_id": 1, "course_id": 2},
                    {"student_id": 1, "course_id": 3},
                    {"student_id": 1, "course_id": 4},
                    {"student_id": 2, "course_id": 2},
                    {"student_id": 2, "course_id": 4},
                ],
            )

    try:
        yield async_session
    finally:
        await engine.dispose()


@pytest.fixture
def m2m_session_factory(m2m_session_maker):
    def _factory():
        return m2m_session_maker()

    return _factory


@pytest.fixture
def m2m_diagram(m2m_session_factory):
    async def get_all_students() -> list[StudentEntity]:
        async with m2m_session_factory() as session:
            rows = (
                await session.execute(select(StudentOrm).order_by(StudentOrm.id))
            ).scalars().all()
        return [StudentEntity.model_validate(r) for r in rows]

    relationship_entities = build_relationship(
        mappings=[
            Mapping(entity=StudentEntity, orm=StudentOrm),
            Mapping(entity=CourseEntity, orm=CourseOrm),
        ],
        session_factory=m2m_session_factory,
    )

    qm_entities = [
        Entity(
            kls=StudentEntity,
            queries=[
                QueryConfig(
                    method=get_all_students,
                    name="students",
                    description="Get all students",
                ),
            ],
        ),
    ]

    d = ErDiagram(entities=qm_entities).add_relationship(relationship_entities)
    config_global_resolver(d)
    return d


class TestManyToManyPagination:
    """Test pagination on many-to-many relationships via secondary tables."""

    def test_m2m_pagination_types_in_sdl(self, m2m_diagram):
        """M2M field should produce a Result type with limit/offset args in SDL."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )
        sdl = handler.schema_builder.build_schema()

        # Result type for CourseEntity
        assert "type CourseEntityResult" in sdl
        assert "items: [CourseEntity!]!" in sdl
        assert "pagination: Pagination!" in sdl

        # M2M field with pagination args
        assert "courses(limit: Int, offset: Int): CourseEntityResult!" in sdl

    def test_m2m_raw_list_when_pagination_disabled(self, m2m_diagram):
        """M2M field should be a raw list when pagination is disabled."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
        )
        sdl = handler.schema_builder.build_schema()

        assert "courses: [CourseEntity!]!" in sdl
        assert "type CourseEntityResult" not in sdl

    @pytest.mark.asyncio
    async def test_m2m_default_page_size(self, m2m_diagram):
        """M2M without explicit limit/offset should use default page_size=20."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ studentEntityStudents { id name courses { items { title } pagination { has_more } } } }"
        )

        assert result["errors"] is None
        students = result["data"]["studentEntityStudents"]
        assert len(students) == 3

        # Alice: 4 courses, default page_size=20 → all returned
        alice = students[0]
        assert alice["name"] == "Alice"
        assert len(alice["courses"]["items"]) == 4
        assert alice["courses"]["pagination"]["has_more"] is False

        # Bob: 2 courses
        bob = students[1]
        assert len(bob["courses"]["items"]) == 2
        assert bob["courses"]["pagination"]["has_more"] is False

        # Carol: 0 courses
        carol = students[2]
        assert len(carol["courses"]["items"]) == 0
        assert carol["courses"]["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_m2m_limit_results(self, m2m_diagram):
        """M2M with limit should restrict results per parent."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ studentEntityStudents { id name courses(limit: 2) { items { title } pagination { has_more } } } }"
        )

        assert result["errors"] is None
        students = result["data"]["studentEntityStudents"]

        # Alice: 4 courses, limit=2 → 2 items, has_more=True
        alice = students[0]
        assert len(alice["courses"]["items"]) == 2
        assert alice["courses"]["pagination"]["has_more"] is True

        # Bob: 2 courses, limit=2 → 2 items, has_more=False
        bob = students[1]
        assert len(bob["courses"]["items"]) == 2
        assert bob["courses"]["pagination"]["has_more"] is False

        # Carol: 0 courses, limit=2 → 0 items, has_more=False
        carol = students[2]
        assert len(carol["courses"]["items"]) == 0
        assert carol["courses"]["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_m2m_total_count(self, m2m_diagram):
        """M2M total_count should reflect the full association count."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ studentEntityStudents { id courses(limit: 1) { items { title } pagination { has_more total_count } } } }"
        )

        assert result["errors"] is None
        students = result["data"]["studentEntityStudents"]

        # Alice: 4 total
        assert students[0]["courses"]["pagination"]["total_count"] == 4
        assert len(students[0]["courses"]["items"]) == 1
        assert students[0]["courses"]["pagination"]["has_more"] is True

        # Bob: 2 total
        assert students[1]["courses"]["pagination"]["total_count"] == 2
        assert students[1]["courses"]["pagination"]["has_more"] is True

        # Carol: 0 total
        assert students[2]["courses"]["pagination"]["total_count"] == 0
        assert students[2]["courses"]["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_m2m_offset_pagination(self, m2m_diagram):
        """M2M offset-based pagination should return correct page."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        # Page 1: limit=2, offset=0
        result = await handler.execute(
            "{ studentEntityStudents { id courses(limit: 2, offset: 0) { items { id title } pagination { has_more total_count } } } }"
        )

        assert result["errors"] is None
        alice = result["data"]["studentEntityStudents"][0]
        page1_ids = [c["id"] for c in alice["courses"]["items"]]
        assert len(page1_ids) == 2
        assert alice["courses"]["pagination"]["has_more"] is True

        # Page 2: limit=2, offset=2
        result2 = await handler.execute(
            "{ studentEntityStudents { id courses(limit: 2, offset: 2) { items { id title } pagination { has_more total_count } } } }"
        )

        assert result2["errors"] is None
        alice2 = result2["data"]["studentEntityStudents"][0]
        page2_ids = [c["id"] for c in alice2["courses"]["items"]]
        assert len(page2_ids) == 2
        assert alice2["courses"]["pagination"]["has_more"] is False

        # No overlap between pages
        assert set(page1_ids).isdisjoint(set(page2_ids))

    @pytest.mark.asyncio
    async def test_m2m_per_parent_isolation(self, m2m_diagram):
        """Each parent should only see its own M2M children."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ studentEntityStudents { id name courses(limit: 10) { items { id title } } } }"
        )

        assert result["errors"] is None
        students = result["data"]["studentEntityStudents"]

        # Alice (id=1): courses 1,2,3,4
        alice_courses = {c["id"] for c in students[0]["courses"]["items"]}
        assert alice_courses == {1, 2, 3, 4}

        # Bob (id=2): courses 2,4
        bob_courses = {c["id"] for c in students[1]["courses"]["items"]}
        assert bob_courses == {2, 4}

        # Carol (id=3): no courses
        carol_courses = {c["id"] for c in students[2]["courses"]["items"]}
        assert carol_courses == set()

    @pytest.mark.asyncio
    async def test_m2m_offset_exceeds_total(self, m2m_diagram):
        """When offset > total, items should be empty but total_count correct."""
        handler = GraphQLHandler(
            m2m_diagram,
            enable_from_attribute_in_type_adapter=True,
            enable_pagination=True,
        )

        result = await handler.execute(
            "{ studentEntityStudents { id courses(limit: 1, offset: 100) { items { title } pagination { has_more total_count } } } }"
        )

        assert result["errors"] is None
        students = result["data"]["studentEntityStudents"]

        # Alice: 4 total but offset=100 → empty
        alice = students[0]
        assert alice["courses"]["items"] == []
        assert alice["courses"]["pagination"]["total_count"] == 4
        assert alice["courses"]["pagination"]["has_more"] is False


# =====================================
# Test: ScopeNode.to_scope_filter
# =====================================


class TestScopeNodeToFilter:
    """Test ScopeNode.to_scope_filter converts scope tree nodes to ScopeFilter."""

    def test_node_with_ids(self):
        from pydantic_resolve.types import ScopeFilter, ScopeNode

        node = ScopeNode(type='articles', ids=[1, 2, 3])
        result = node.to_scope_filter()
        assert isinstance(result, ScopeFilter)
        assert result.ids == frozenset({1, 2, 3})

    def test_node_with_empty_ids(self):
        from pydantic_resolve.types import ScopeFilter, ScopeNode

        node = ScopeNode(type='articles', ids=[])
        result = node.to_scope_filter()
        assert isinstance(result, ScopeFilter)
        assert result.ids is None  # empty list → None (unconstrained)

    def test_node_with_none_ids(self):
        from pydantic_resolve.types import ScopeFilter, ScopeNode

        node = ScopeNode(type='articles')
        result = node.to_scope_filter()
        assert isinstance(result, ScopeFilter)
        assert result.ids is None

    def test_node_with_filter_fn(self):
        from pydantic_resolve.types import ScopeNode

        fn = lambda q: q
        node = ScopeNode(type='articles', filter_fn=fn)
        result = node.to_scope_filter()
        assert result.filter_fn is fn


# =====================================
# Test: Paged resolve method with scope
# =====================================


class TestPagedResolveMethodWithScope:
    """Test _attach_paged_resolve_methods integrates scope into LoadCommand."""

    def _make_model_with_resolve(self, scope_tree=None):
        """Build a dynamic model with a paginated resolve method.

        Returns (model_class, captured_keys) where captured_keys collects
        all keys passed to loader.load().
        """
        from pydantic import BaseModel
        from pydantic_resolve.graphql.pagination.types import PageArgs
        from pydantic_resolve.types import LoadCommand
        from pydantic_resolve.utils.depend import Loader
        from pydantic_resolve.utils.er_diagram import Relationship, resolve_scope_filter

        captured_keys = []

        async def fake_page_loader(keys):
            return [[] for _ in keys]

        def fake_key_builder(fk_value, instance, field_name):
            page_args = getattr(instance, f'_pag_{field_name}', None)
            if page_args is None:
                page_args = PageArgs(default_page_size=20)
            return LoadCommand(fk_value=fk_value, page_args=page_args)

        rel = Relationship(
            fk='author_id',
            target=list,
            name='articles',
            loader=fake_page_loader,
            page_loader=fake_page_loader,
        )
        rel.key_builder = fake_key_builder

        # Build the same closure as _attach_paged_resolve_methods
        def _make_resolve_method(r, fld_name, b):
            def resolve_method(self, loader=Loader(r.page_loader)):
                fk = getattr(self, r.fk)
                if fk is None:
                    return None

                key_obj = b(fk, self, fld_name)

                scope_tree = getattr(self, '_access_scope_tree', None)
                scope_filter = resolve_scope_filter(scope_tree, fld_name)

                if scope_filter is not None:
                    from pydantic_resolve.types import LoadCommand
                    if isinstance(key_obj, LoadCommand):
                        key_obj = LoadCommand(
                            fk_value=key_obj.fk_value,
                            page_args=key_obj.page_args,
                            scope_filter=scope_filter,
                        )
                    else:
                        key_obj = LoadCommand(fk_value=fk, scope_filter=scope_filter)

                captured_keys.append(key_obj)
                return []
            return resolve_method

        method = _make_resolve_method(rel, 'articles', fake_key_builder)
        method.__name__ = 'resolve_articles'

        class FakeModel(BaseModel):
            author_id: int = 1
            articles: list = []

            resolve_articles = method

        return FakeModel, captured_keys

    def test_no_scope_tree_produces_loadcommand_without_scope(self):
        """When no _access_scope_tree, key is LoadCommand with only page_args."""
        from pydantic_resolve.types import LoadCommand

        ModelCls, captured = self._make_model_with_resolve()

        instance = ModelCls(author_id=42)
        # No _access_scope_tree attribute
        instance.resolve_articles()

        assert len(captured) == 1
        key = captured[0]
        assert isinstance(key, LoadCommand)
        assert key.fk_value == 42
        assert key.page_args is not None
        assert key.scope_filter is None

    def test_rbac_scope_adds_scope_filter(self):
        """When _access_scope_tree has ScopeNode list, scope_filter.ids is attached."""
        from pydantic_resolve.types import LoadCommand, ScopeNode

        ModelCls, captured = self._make_model_with_resolve()

        instance = ModelCls(author_id=42)
        instance._access_scope_tree = [ScopeNode(type='articles', ids=[1, 3, 5])]
        instance.resolve_articles()

        assert len(captured) == 1
        key = captured[0]
        assert isinstance(key, LoadCommand)
        assert key.fk_value == 42
        assert key.page_args is not None  # pagination still present
        assert key.scope_filter is not None
        assert key.scope_filter.ids == frozenset({1, 3, 5})

    def test_scope_for_unrelated_field_is_ignored(self):
        """When _access_scope_tree has no entry for the resolved field, no scope is added."""
        from pydantic_resolve.types import LoadCommand, ScopeNode

        ModelCls, captured = self._make_model_with_resolve()

        instance = ModelCls(author_id=42)
        instance._access_scope_tree = [ScopeNode(type='other_field', ids=[1])]
        instance.resolve_articles()

        assert len(captured) == 1
        key = captured[0]
        assert isinstance(key, LoadCommand)
        assert key.scope_filter is None

    def test_fk_none_returns_none(self):
        """When FK is None, resolve returns None without calling loader."""
        ModelCls, captured = self._make_model_with_resolve()

        instance = ModelCls(author_id=0)
        instance.author_id = None  # type: ignore
        result = instance.resolve_articles()

        assert result is None
        assert len(captured) == 0
