"""
Tests for access control scope propagation and consumption.

Validates the full chain:
1. Scope tree structure (list-of-nodes + 'all'/'empty' + ScopeFilter)
2. inject_access_scope resolved_hook (scope propagation)
3. AutoLoad resolve method consuming scope → LoadCommand
4. Loader receiving LoadCommand with scope_filter
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
from pydantic_resolve.types import LoadCommand, ScopeFilter, ScopeNode
from pydantic_resolve.utils.dataloader import build_list


# =====================================
# Scope Tree Structure
# =====================================
#
# _access_scope_tree can be:
# - None: no scope constraint (default)
# - 'all': global permission, unconstrained loading
# - 'empty': no permission, return empty
# - list[ScopeNode]: scoped access as list-of-nodes
#
# Each ScopeNode: type, ids, apply, children
# - type: relationship name (field name)
# - ids: None=unconstrained, []=empty, [1,2,...]=concrete IDs
# - apply: ABAC filter function (optional)
# - children: nested scope nodes (optional)


# =====================================
# inject_access_scope hook
# =====================================


def inject_access_scope(parent, field_name, result):
    """resolved-hook: propagate scope tree children to resolved items.

    Called after each resolve method, before recursive traversal.
    Reads _access_scope_tree from parent, finds entries matching field_name,
    and injects children into resolved items by item ID.
    """
    scope_tree = getattr(parent, '_access_scope_tree', None)
    if not scope_tree or scope_tree in ('all', 'empty'):
        return

    if not isinstance(scope_tree, list):
        return

    matched = [e for e in scope_tree if e.type == field_name]
    if not matched:
        return

    items = _get_items(result)
    if not items:
        all_children = []
        for entry in matched:
            if entry.children:
                all_children.extend(entry.children)
        if all_children and hasattr(result, '__dict__'):
            object.__setattr__(result, '_access_scope_tree', all_children)
        return

    id_to_children: dict[int, list] = {}
    for entry in matched:
        entry_ids = entry.ids
        children = entry.children
        if entry_ids is None:
            for item in items:
                iid = getattr(item, 'id', None)
                if iid is not None and children:
                    id_to_children.setdefault(iid, []).extend(children)
        else:
            for iid in entry_ids:
                if children:
                    id_to_children.setdefault(iid, []).extend(children)

    for item in items:
        iid = getattr(item, 'id', None)
        child_scope = id_to_children.get(iid)
        if child_scope is not None:
            object.__setattr__(item, '_access_scope_tree', child_scope)


def _get_items(result):
    """Extract items from result (list or paginated)."""
    items = getattr(result, 'items', None)
    if items:
        return items
    if isinstance(result, list):
        return result
    return None


# =====================================
# Layer 1: inject_access_scope unit tests
# =====================================


class Project(BaseModel):
    id: int
    name: str = ""


class Document(BaseModel):
    id: int
    title: str = ""


class TestInjectAccessScope:
    """Test inject_access_scope hook propagates scope correctly."""

    def test_rbac_scope_propagation_by_id(self):
        """RBAC: scope is matched to children by item ID via list-of-nodes."""
        parent = Project(id=0)
        parent._access_scope_tree = [
            ScopeNode(
                type='projects',
                ids=[1],
                children=[
                    ScopeNode(type='documents', ids=[10, 11]),
                ],
            ),
            ScopeNode(
                type='projects',
                ids=[3],
                children=None,
            ),
        ]

        children = [Project(id=1), Project(id=2), Project(id=3)]
        inject_access_scope(parent, 'projects', children)

        # Project 1: has nested scope
        assert getattr(children[0], '_access_scope_tree', None) == [
            ScopeNode(type='documents', ids=[10, 11]),
        ]
        # Project 2: not in scope → no attribute set
        assert not hasattr(children[1], '_access_scope_tree')
        # Project 3: in scope but children=None → no attribute set
        assert not hasattr(children[2], '_access_scope_tree')

    def test_no_scope_tree_is_noop(self):
        """Parent without _access_scope_tree → nothing happens."""
        parent = Project(id=0)
        children = [Project(id=1)]
        inject_access_scope(parent, 'projects', children)
        assert not hasattr(children[0], '_access_scope_tree')

    def test_all_literal_is_noop(self):
        """Parent with 'all' scope → hook does nothing."""
        parent = Project(id=0)
        parent._access_scope_tree = 'all'
        children = [Project(id=1)]
        inject_access_scope(parent, 'projects', children)
        assert not hasattr(children[0], '_access_scope_tree')

    def test_empty_literal_is_noop(self):
        """Parent with 'empty' scope → hook does nothing."""
        parent = Project(id=0)
        parent._access_scope_tree = 'empty'
        children = [Project(id=1)]
        inject_access_scope(parent, 'projects', children)
        assert not hasattr(children[0], '_access_scope_tree')

    def test_unrelated_field_is_skipped(self):
        """scope_tree has entry for different type → no propagation."""
        parent = Project(id=0)
        parent._access_scope_tree = [
            ScopeNode(type='other_field', ids=[1]),
        ]

        children = [Project(id=1)]
        inject_access_scope(parent, 'projects', children)
        assert not hasattr(children[0], '_access_scope_tree')

    def test_result_model_with_items(self):
        """Paginated Result model with .items attribute."""
        parent = Project(id=0)
        parent._access_scope_tree = [
            ScopeNode(
                type='projects',
                ids=[1],
                children=[
                    ScopeNode(type='documents', ids=[10]),
                ],
            ),
        ]

        class Result(BaseModel):
            items: list

        result = Result(items=[Project(id=1), Project(id=2)])
        inject_access_scope(parent, 'projects', result)

        assert result.items[0]._access_scope_tree == [
            ScopeNode(type='documents', ids=[10]),
        ]
        assert not hasattr(result.items[1], '_access_scope_tree')


# =====================================
# Entities for end-to-end tests
# =====================================

BaseEntity = base_entity()

# Shared captured keys for inspecting loader inputs
_captured = {'projects': [], 'documents': []}


async def project_loader(keys):
    """Mock project loader that captures LoadCommand keys."""
    _captured['projects'] = list(keys)

    # Unpack keys
    fk_values = []
    for k in keys:
        if isinstance(k, LoadCommand):
            fk_values.append(k.fk_value)
        else:
            fk_values.append(k)

    # Mock data: all projects belong to dept_id=1
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
# Layer 2: Resolver end-to-end (RBAC)
# =====================================


class TestResolverEndToEndRBAC:
    """Test full RBAC scope chain: scope tree → hook → AutoLoad → LoadCommand → loader."""

    @pytest.mark.asyncio
    async def test_rbac_scope_filters_projects(self):
        """RBAC scope tree limits which projects are loaded."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        scope_tree = [
            ScopeNode(
                type='projects',
                ids=[1],
                children=[
                    ScopeNode(type='documents', ids=[10]),
                ],
            ),
            ScopeNode(
                type='projects',
                ids=[3],
                children=None,
            ),
        ]

        root = DeptView(id=1, name="Engineering")
        object.__setattr__(root, '_access_scope_tree', scope_tree)

        resolver = Resolver(
            resolved_hooks=[inject_access_scope],
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

        # Verify all 3 projects returned by loader (loader doesn't filter by scope here)
        assert len(result.projects) == 3

        # Verify hook propagated scope to correct children
        p1 = result.projects[0]
        p2 = result.projects[1]
        p3 = result.projects[2]

        assert p1.id == 1
        assert p1._access_scope_tree == [
            ScopeNode(type='documents', ids=[10]),
        ]

        assert p2.id == 2
        assert not hasattr(p2, '_access_scope_tree')

        assert p3.id == 3
        # p3 has children=None in scope → no _access_scope_tree injected
        assert not hasattr(p3, '_access_scope_tree')

    @pytest.mark.asyncio
    async def test_rbac_nested_scope_filters_documents(self):
        """Nested RBAC scope: project 1 only loads document 10."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        scope_tree = [
            ScopeNode(
                type='projects',
                ids=[1],
                children=[
                    ScopeNode(type='documents', ids=[10]),
                ],
            ),
            ScopeNode(
                type='projects',
                ids=[3],
                children=None,
            ),
        ]

        root = DeptView(id=1, name="Engineering")
        object.__setattr__(root, '_access_scope_tree', scope_tree)

        resolver = Resolver(
            resolved_hooks=[inject_access_scope],
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        # Verify document_loader received keys for each project
        assert len(_captured['documents']) >= 2  # at least project 1 and project 3

        # Find the key for project_id=1 (should have scope_filter)
        p1_doc_key = None
        for k in _captured['documents']:
            fk = k.fk_value if isinstance(k, LoadCommand) else k
            if fk == 1:
                p1_doc_key = k
                break

        assert p1_doc_key is not None
        assert isinstance(p1_doc_key, LoadCommand)
        assert p1_doc_key.scope_filter is not None
        assert p1_doc_key.scope_filter.ids == frozenset({10})

        # Project 1: mock loader returns all 3 docs (doesn't filter by scope)
        p1 = result.projects[0]
        assert p1.id == 1
        assert len(p1.documents) == 3  # mock returns all

        # Project 2: no scope → all documents loaded normally
        p2 = result.projects[1]
        assert p2.id == 2
        assert len(p2.documents) == 1
        assert p2.documents[0].id == 20

        # Project 3: has scope but children=None → no constraint on documents
        p3 = result.projects[2]
        assert p3.id == 3
        assert len(p3.documents) == 1
        assert p3.documents[0].id == 30


# =====================================
# Layer 3: Resolver end-to-end ('all' / ScopeFilter)
# =====================================


class TestResolverEndToEndABAC:
    """Test 'all' literal and ScopeFilter propagation through the full chain."""

    @pytest.mark.asyncio
    async def test_all_literal_loads_everything(self):
        """'all' scope loads all data without constraint."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        root = DeptView(id=1, name="Engineering")
        object.__setattr__(root, '_access_scope_tree', 'all')

        resolver = Resolver(
            resolved_hooks=[inject_access_scope],
            enable_from_attribute_in_type_adapter=True,
        )
        result = await resolver.resolve(root)

        # 'all' → ScopeFilter(ids=None) → LoadCommand with unconstrained scope
        assert len(_captured['projects']) == 1
        key = _captured['projects'][0]
        assert isinstance(key, LoadCommand)
        assert key.scope_filter is not None
        assert key.scope_filter.ids is None  # unconstrained

        # All projects loaded
        assert len(result.projects) == 3
        # All documents loaded for each project
        for proj in result.projects:
            assert len(proj.documents) >= 1

    @pytest.mark.asyncio
    async def test_no_scope_loads_everything(self):
        """Without scope_tree, all data is loaded normally."""
        from pydantic_resolve import Resolver

        _captured['projects'].clear()
        _captured['documents'].clear()

        root = DeptView(id=1, name="Engineering")
        # No _access_scope_tree set

        resolver = Resolver(
            resolved_hooks=[inject_access_scope],
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
