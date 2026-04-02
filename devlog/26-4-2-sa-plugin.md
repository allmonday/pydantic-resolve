# Plan: Auto-build DataLoader from ORM Relationships

## Summary

从 SQLAlchemy ORM 的 relationship 定义自动生成 `Relationship` 和 DataLoader 实现，通过 `build_relationship()` + `ErDiagram.add_relationship()` 组合使用。

本版 plan 解决三个关键语义问题：

1. **不把 ORM 的 `uselist` 映射到 `Relationship.load_many`**（避免触发 `loader.load_many(...)` 的错误语义）
2. **to-many 关系统一产出 `target=list[TargetDTO]`**（对齐 AutoLoad 类型检查和 GraphQL 类型映射）
3. **为每个关系生成唯一身份的 DataLoader class**（避免 loader 缓存键冲突）

## Usage Example

```python
from pydantic_resolve.contrib.sqlalchemy import build_relationship

# DTO definitions (Pydantic BaseModel, with from_attributes=True)
class StudentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    school_id: int

class SchoolDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

# Build from ORM mappings
diagram = ErDiagram(configs=existing_configs)
diagram = diagram.add_relationship(
    build_relationship(
        mappings=[(StudentDTO, StudentOrm), (SchoolDTO, SchoolOrm)],
        session_factory=get_async_session,
    )
)
config_global_resolver(diagram)
```

## File Changes

### New Files

| File | Purpose |
|------|---------|
| `pydantic_resolve/contrib/__init__.py` | Empty, namespace package marker |
| `pydantic_resolve/contrib/sqlalchemy/__init__.py` | Export `build_relationship` |
| `pydantic_resolve/contrib/sqlalchemy/inspector.py` | ORM relationship inspection + `build_relationship` entry point |
| `pydantic_resolve/contrib/sqlalchemy/loader.py` | `create_many_to_one_loader`, `create_one_to_many_loader`, `create_many_to_many_loader` factories |

### Modified Files

| File | Change |
|------|--------|
| `pydantic_resolve/utils/er_diagram.py` | Add `ErDiagram.add_relationship()` method |
| `pyproject.toml` | Add `[project.optional-dependencies] sqlalchemy = [...]` |

### Test Files

| File | Purpose |
|------|---------|
| `tests/contrib/__init__.py` | Empty |
| `tests/contrib/sqlalchemy/__init__.py` | Empty |
| `tests/contrib/sqlalchemy/conftest.py` | Async engine/session fixtures with aiosqlite |
| `tests/contrib/sqlalchemy/test_inspector.py` | ORM inspection tests (including M2M) |
| `tests/contrib/sqlalchemy/test_loader.py` | Loader generation + execution tests (including M2M) |
| `tests/contrib/sqlalchemy/test_build_relationship.py` | End-to-end integration tests |
| `tests/contrib/sqlalchemy/test_add_relationship.py` | ErDiagram.add_relationship merge tests |

---

## Implementation Details

### Step 1: `pydantic_resolve/contrib/sqlalchemy/loader.py`

Three loader factory functions.

Generated loaders should be **DataLoader subclasses with unique class names**, not plain closure functions.

Reason: loader manager caches by `module + qualname`; plain closures from the same factory can collide.

Shared helper:

```python
def _build_loader_identity(source_orm_kls, rel_name: str, suffix: str) -> str:
    # Example: Student_courses_M2M
    return f"{source_orm_kls.__name__}_{rel_name}_{suffix}"


def _finalize_loader_class(cls, identity: str):
    cls.__name__ = f"SA_{identity}"
    cls.__qualname__ = cls.__name__
    cls.__module__ = __name__
    return cls
```

**create_many_to_one_loader** (ManyToOne / OneToOne):
```python
def create_many_to_one_loader(
    *,
    source_orm_kls,
    rel_name,
    target_orm_kls,
    target_dto_kls,
    target_remote_col_name,
    session_factory,
):
    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            async with session_factory() as session:
                stmt = select(target_orm_kls).where(
                    getattr(target_orm_kls, target_remote_col_name).in_(keys)
                )
                rows = (await session.scalars(stmt)).all()

            lookup = {getattr(r, target_remote_col_name): r for r in rows}
            return [
                target_dto_kls.model_validate(lookup[k]) if k in lookup else None
                for k in keys
            ]

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "M2O"),
    )
```

**create_one_to_many_loader** (OneToMany):
```python
def create_one_to_many_loader(
    *,
    source_orm_kls,
    rel_name,
    target_orm_kls,
    target_dto_kls,
    target_fk_col_name,
    session_factory,
):
    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            async with session_factory() as session:
                stmt = select(target_orm_kls).where(
                    getattr(target_orm_kls, target_fk_col_name).in_(keys)
                )
                rows = (await session.scalars(stmt)).all()

            grouped = defaultdict(list)
            for row in rows:
                grouped[getattr(row, target_fk_col_name)].append(
                    target_dto_kls.model_validate(row)
                )

            return [grouped.get(k, []) for k in keys]

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "O2M"),
    )
```

**create_many_to_many_loader** (ManyToMany):
```python
def create_many_to_many_loader(
    *,
    source_orm_kls,
    rel_name,
    target_orm_kls,
    target_dto_kls,
    secondary_table,
    secondary_local_col_name,
    secondary_remote_col_name,
    target_match_col_name,
    session_factory,
):
    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            async with session_factory() as session:
                join_stmt = select(secondary_table).where(
                    getattr(secondary_table.c, secondary_local_col_name).in_(keys)
                )
                join_rows = (await session.execute(join_stmt)).all()

                target_keys = list(
                    {
                        getattr(row, secondary_remote_col_name)
                        for row in join_rows
                    }
                )
                if not target_keys:
                    return [[] for _ in keys]

                target_stmt = select(target_orm_kls).where(
                    getattr(target_orm_kls, target_match_col_name).in_(target_keys)
                )
                target_rows = (await session.scalars(target_stmt)).all()
                target_map = {
                    getattr(row, target_match_col_name): target_dto_kls.model_validate(row)
                    for row in target_rows
                }

            grouped = defaultdict(list)
            for jr in join_rows:
                target_obj = target_map.get(getattr(jr, secondary_remote_col_name))
                if target_obj is not None:
                    grouped[getattr(jr, secondary_local_col_name)].append(target_obj)

            return [grouped.get(k, []) for k in keys]

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "M2M"),
    )
```

Notes:

- All three loaders return **result list aligned with incoming keys** (`len(result) == len(keys)`).
- ORM relationships should use `loader.load(fk)` path (do not rely on `relationship.load_many=True`).

### Step 2: `pydantic_resolve/contrib/sqlalchemy/inspector.py`

Main entry point `build_relationship` + internal helpers.

**`build_relationship(mappings, session_factory) -> list[Entity]`:**

1. Build `orm_to_dto` dict: `{OrmKls: DtoKls}`
2. For each (DTO, ORM) pair, call `_inspect_orm_relationships`
3. Collect Entity objects, return those with at least one relationship

**`_inspect_orm_relationships(orm_kls, orm_to_dto, session_factory) -> list[Relationship]`:**

1. `from sqlalchemy import inspect` (lazy import)
2. `mapper = inspect(orm_kls)`
3. For each `rel` in `mapper.relationships`:
   - `target_orm = rel.mapper.class_`
   - Look up target DTO in `orm_to_dto`. Skip + warn if not found.
     - Branch by `rel.direction`:
        - **MANYTOONE** (includes one-to-one relationship when `uselist=False`)
             - Use `_expect_single_pair(rel.local_remote_pairs)` -> `(local_col, remote_col)`
             - `fk_field = local_col.key`
             - `target = target_dto`
             - `loader = create_many_to_one_loader(..., target_remote_col_name=remote_col.key, ...)`
         - **ONETOMANY**
             - Use `_expect_single_pair(rel.local_remote_pairs)` -> `(local_col, remote_col)`
             - `fk_field = local_col.key` (usually source PK)
             - `target = list[target_dto]`
             - `loader = create_one_to_many_loader(..., target_fk_col_name=remote_col.key, ...)`
         - **MANYTOMANY**
             - `secondary_table = rel.secondary` (must exist)
             - Use `_expect_single_pair(rel.synchronize_pairs)` -> `(source_col, secondary_local_col)`
             - Use `_expect_single_pair(rel.secondary_synchronize_pairs)` -> `(target_col, secondary_remote_col)`
             - `fk_field = source_col.key`
             - `target = list[target_dto]`
             - `loader = create_many_to_many_loader(...,
                 secondary_local_col_name=secondary_local_col.key,
                 secondary_remote_col_name=secondary_remote_col.key,
                 target_match_col_name=target_col.key,
                 ...)`
     - Build `Relationship(fk=fk_field, target=target, name=rel.key, loader=loader, load_many=False)`

**Helper `_expect_single_pair(pairs, message) -> tuple[col, col]`:**
- if `len(pairs) != 1`: raise `NotImplementedError(message)`
- returns the single pair

This helper is used to make unsupported scenarios explicit (composite FK / composite PK / complex join conditions).

### Step 3: `ErDiagram.add_relationship()` in `er_diagram.py`

Add method to existing `ErDiagram` class. Returns new `ErDiagram` (immutable pattern).

**Merge logic:**
1. Build `existing_map: dict[type, Entity]` from `self.configs`
2. For each existing config, check if incoming entities has matching kls:
    - Merge relationships by `name` (raise on duplicate)
    - Merge queries by method name (raise on duplicate)
    - Merge mutations by method name (raise on duplicate)
3. Append new entities whose kls is not in existing configs
4. Return `ErDiagram(configs=merged_configs, description=self.description)`

Method signature:

```python
def add_relationship(self, entities: list[Entity]) -> "ErDiagram":
     ...
```

### Step 4: `pyproject.toml`

Add optional dependency group:

```toml
[project.optional-dependencies]
sqlalchemy = [
    "sqlalchemy[asyncio]>=2.0.7,<3.0.0"
]
```

Note: `sqlalchemy[asyncio]` is already in `[project.optional-dependencies.dev]`, so this only adds the user-facing opt-in group.

---

## Key Design Decisions

1. **DTO requires `from_attributes=True`**: Loader uses `DTO.model_validate(orm_instance)` for conversion
2. **Async only**: `session_factory` is a callable returning `AsyncContextManager[AsyncSession]`
3. **ORM relation always uses `loader.load(...)` path**: `Relationship.load_many` stays `False`
4. **To-many relation target is always `list[TargetDTO]`**
5. **Loader identity must be unique per relationship**: avoid cache key collision in loader manager
6. **M2M metadata extraction uses `synchronize_pairs` + `secondary_synchronize_pairs`** (not `local_remote_pairs`)
7. **Lazy SQLAlchemy import**: all `sqlalchemy` imports remain in `contrib/sqlalchemy/*`
8. **Scope bounded by mappings**: only process relationships where source/target ORM both have DTO mapping
9. **Unsupported in v1**: composite FK, composite PK, and complex custom joins

## Edge Cases

- **Self-referential**: Same ORM class as source and target - works, `orm_to_dto` lookup finds itself
- **Multiple rels to same target**: e.g., `created_by` and `reviewed_by` both -> User - works, each has unique `rel.key`
- **No relationships on ORM**: Entity with empty relationships list - filtered out, not returned
- **Session lifecycle**: One session per batch (`batch_load_fn` opens/closes session)
- **M2M with no matches**: Returns `[[] for _ in keys]` when join table has no matching rows
- **Many-to-one to non-PK unique column**: supported (uses relationship remote column, not forced PK lookup)
- **Unmapped target ORM**: warning + skip relation
- **Duplicate merge in `add_relationship`**: explicit error for relationship/query/mutation name conflicts

## Implementation Order

1. Create `pydantic_resolve/contrib/__init__.py` (empty)
2. Create `pydantic_resolve/contrib/sqlalchemy/loader.py` (three DataLoader class factories + identity helpers)
3. Create `pydantic_resolve/contrib/sqlalchemy/inspector.py` (inspection + direction-based builder)
4. Create `pydantic_resolve/contrib/sqlalchemy/__init__.py` (exports)
5. Modify `pydantic_resolve/utils/er_diagram.py` (add `add_relationship`)
6. Modify `pyproject.toml` (add sqlalchemy optional dep)
7. Create tests:
    - inspector direction and pair extraction tests
    - loader identity uniqueness tests (cache key safety)
    - build_relationship integration tests (M2O/O2M/M2M)
    - add_relationship merge conflict tests
8. Run tests and iterate
