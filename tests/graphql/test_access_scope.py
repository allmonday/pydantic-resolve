"""
Tests for access control scope propagation and consumption.

Validates the full chain:
1. User scope dict structure (dict[str, ScopeFilter])
2. AutoLoad resolve method consuming scope from context → LoadCommand
3. Loader receiving LoadCommand with scope_filter
"""

import pytest
from typing import Annotated, Optional
from pydantic import BaseModel

from pydantic_resolve import (
    Relationship,
    base_entity,
    config_global_resolver,
    reset_global_resolver,
)
from pydantic_resolve.types import LoadCommand, ScopeFilter
from pydantic_resolve.utils.dataloader import build_list


# =====================================
# Entities for end-to-end tests
# =====================================

BaseEntity = base_entity()

# Shared captured keys for inspecting loader inputs
_captured = {'projects': [], 'documents': []}


async def project_loader(keys):
    """Mock project loader that captures LoadCommand keys."""
    _captured['projects'] = list(keys)

    fk_values = []
    for k in keys:
        if isinstance(k, LoadCommand):
            fk_values.append(k.fk_value)
        else:
            fk_values.append(k)

    all_projects = [
        ProjectEntity(id=1, dept_id=1, name="P1"),
        ProjectEntity(id=2, dept_id=1, name="P2"),
        ProjectEntity(id=3, dept_id=1, name="P3"),
    ]
    return build_list(all_projects, fk_values, lambda p: p.dept_id)


async def document_loader(keys):
    """Mock document loader that captures LoadCommand keys."""
    _captured['documents'] = list(keys)

    fk_values = []
    for k in keys:
        if isinstance(k, LoadCommand):
            fk_values.append(k.fk_value)
        else:
            fk_values.append(k)

    all_docs = [
        DocumentEntity(id=10, project_id=1, title="D10"),
        DocumentEntity(id=11, project_id=1, title="D11"),
        DocumentEntity(id=12, project_id=1, title="D12"),
        DocumentEntity(id=20, project_id=2, title="D20"),
        DocumentEntity(id=30, project_id=3, title="D30"),
    ]
    return build_list(all_docs, fk_values, lambda d: d.project_id)


class DocumentEntity(BaseModel, BaseEntity):
    __relationships__ = []
    id: int
    project_id: int
    title: str


class ProjectEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='id',
            name='documents',
            target=list[DocumentEntity],
            loader=document_loader,
        )
    ]
    id: int
    dept_id: int
    name: str


class DeptEntity(BaseModel, BaseEntity):
    __relationships__ = [
        Relationship(
            fk='id',
            name='projects',
            target=list[ProjectEntity],
            loader=project_loader,
        )
    ]
    id: int
    name: str


# Build diagram and AutoLoad
_diagram = BaseEntity.get_diagram()
_diagram.enable_scope()  # Enable scope plugin for access control
AutoLoad = _diagram.create_auto_load()
config_global_resolver(_diagram)


@pytest.fixture(autouse=True)
def _setup_global_resolver():
    """Ensure global resolver is configured for every test in this module."""
    config_global_resolver(_diagram)
    yield


# =====================================
# View models for end-to-end tests
# =====================================


class DocumentView(DocumentEntity):
    pass


class ProjectView(ProjectEntity):
    documents: Annotated[list[DocumentView], AutoLoad()] = []


class DeptView(DeptEntity):
    projects: Annotated[list['ProjectView'], AutoLoad()] = []


# =====================================
# Layer 1: Resolver end-to-end (RBAC dict scope)
# =====================================


class TestResolverEndToEndRBAC:
    """Test full RBAC scope chain: context scope → AutoLoad → LoadCommand → loader."""

    @pytest.mark.asyncio
    async def test_rbac_scope_filters_projects(self):
        """RBAC dict scope limits which projects are loaded via scope_filter."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        scope = {"projects": ScopeFilter(ids=frozenset({1, 3}))}

        root = DeptView(id=1, name="Engineering")

        resolver = Resolver(
            user_scope=scope,
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        # Verify project_loader received LoadCommand with scope_filter
        assert len(_captured['projects']) == 1
        key = _captured['projects'][0]
        assert isinstance(key, LoadCommand)
        assert key.fk_value == 1  # dept_id
        assert key.scope_filter is not None
        assert key.scope_filter.ids == frozenset({1, 3})

        # Verify all 3 projects returned by loader (mock doesn't filter by scope)
        assert len(result.projects) == 3

    @pytest.mark.asyncio
    async def test_rbac_nested_scope_filters_documents(self):
        """Dict scope with documents entry: project resolves documents with scope."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        scope = {
            "projects": ScopeFilter(ids=frozenset({1, 3})),
            "documents": ScopeFilter(ids=frozenset({10})),
        }

        root = DeptView(id=1, name="Engineering")

        resolver = Resolver(
            user_scope=scope,
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        # Verify document_loader received keys for each project
        assert len(_captured['documents']) >= 2

        # All doc keys should be LoadCommand (scope is active)
        for k in _captured['documents']:
            assert isinstance(k, LoadCommand)

        # Find the key for project_id=1
        p1_doc_key = None
        for k in _captured['documents']:
            if k.fk_value == 1:
                p1_doc_key = k
                break

        assert p1_doc_key is not None
        assert p1_doc_key.scope_filter.ids == frozenset({10})


# =====================================
# Layer 2: Resolver end-to-end (is_all / no scope)
# =====================================


class TestResolverEndToEndABAC:
    """Test is_all and no-scope propagation through the full chain."""

    @pytest.mark.asyncio
    async def test_is_all_loads_everything(self):
        """is_all=True scope loads all data without constraint."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        scope = {"projects": ScopeFilter(is_all=True)}

        root = DeptView(id=1, name="Engineering")

        resolver = Resolver(
            user_scope=scope,
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        # is_all → LoadCommand with unconstrained scope
        assert len(_captured['projects']) == 1
        key = _captured['projects'][0]
        assert isinstance(key, LoadCommand)
        assert key.scope_filter is not None
        assert key.scope_filter.is_all is True

        # All projects loaded
        assert len(result.projects) == 3
        # All documents loaded for each project
        for proj in result.projects:
            assert len(proj.documents) >= 1

    @pytest.mark.asyncio
    async def test_no_scope_loads_everything(self):
        """Without _user_scope in context, all data is loaded normally (no scope system)."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        root = DeptView(id=1, name="Engineering")
        # No _user_scope in context

        resolver = Resolver(
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        # project_loader received raw FK (not LoadCommand)
        assert len(_captured['projects']) == 1
        key = _captured['projects'][0]
        # Without scope, key is just the raw fk value
        assert not isinstance(key, LoadCommand)

        # All projects loaded
        assert len(result.projects) == 3
        # All documents loaded for each project
        for proj in result.projects:
            assert len(proj.documents) >= 1


# =====================================
# Layer 3: Scope provider auto-injection
# =====================================


class TestScopeProviderAutoInjection:
    """Test scope_provider callback auto-injected by Resolver.resolve()."""

    @pytest.fixture(autouse=True)
    def _setup_provider(self):
        """Set a scope_provider on the module-level diagram for these tests."""
        def _provider(context):
            if context and context.get('role') == 'admin':
                return {"projects": ScopeFilter(is_all=True)}
            if context and context.get('role') == 'restricted':
                return {"projects": ScopeFilter(ids=frozenset({1}))}
            return {}  # no permission

        _diagram._scope_provider = _provider
        yield
        _diagram._scope_provider = None  # clean up

    @pytest.mark.asyncio
    async def test_provider_admin_gets_all(self):
        """scope_provider returns is_all=True for admin role."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()

        root = DeptView(id=1, name="Engineering")
        resolver = Resolver(
            context={'role': 'admin'},
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        assert len(_captured['projects']) == 1
        key = _captured['projects'][0]
        assert isinstance(key, LoadCommand)
        assert key.scope_filter is not None
        assert key.scope_filter.is_all is True

    @pytest.mark.asyncio
    async def test_provider_restricted_gets_filtered(self):
        """scope_provider returns scoped ids for restricted role."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()

        root = DeptView(id=1, name="Engineering")
        resolver = Resolver(
            context={'role': 'restricted'},
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        assert len(_captured['projects']) == 1
        key = _captured['projects'][0]
        assert isinstance(key, LoadCommand)
        assert key.scope_filter.ids == frozenset({1})

    @pytest.mark.asyncio
    async def test_provider_no_role_gets_empty(self):
        """scope_provider returns {} for unknown role → empty scope_filter."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()

        root = DeptView(id=1, name="Engineering")
        resolver = Resolver(
            context={'role': 'unknown'},
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        assert len(_captured['projects']) == 1
        key = _captured['projects'][0]
        assert isinstance(key, LoadCommand)
        assert key.scope_filter.ids == frozenset()  # no permission
