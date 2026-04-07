# Changelog

- **Major (X.0.0)**: Major new features or breaking changes
- **Minor (x.Y.0)**: New features, backward compatible
- **Patch (x.y.Z)**: Bug fixes and minor improvements

## 5.0

### 5.0.0 (2026-4-3)

**BREAKING CHANGES** — `ErDiagram.configs` renamed to `ErDiagram.entities`. See [Migration Guide](./migration.md) for details.

- feat:
  - **ORM relationship auto-discovery**: new `pydantic_resolve/integration` module generates `Relationship` + `DataLoader` from SQLAlchemy, Django, Tortoise ORM model definitions, eliminating hand-written loaders
    - `pydantic_resolve.integration.sqlalchemy` (`pip install pydantic-resolve[sqlalchemy]`)
    - `pydantic_resolve.integration.django` (`pip install pydantic-resolve[django]`)
    - `pydantic_resolve.integration.tortoise` (`pip install pydantic-resolve[tortoise]`)
  - Each ORM adapter supports: Many-to-One, One-to-Many, One-to-One, Reverse One-to-One, Many-to-Many
  - Generated loaders leverage `_query_meta` for field projection (`load_only` / `only`)
  - Per-mapping `filters` and `default_filter` for query filtering
  - DTO required-field validation against ORM scalar fields at setup time
  - **`Mapping` dataclass** (`integration.mapping`): unified ORM-to-DTO mapping descriptor
  - **`ErDiagram.add_relationship()`**: merge ORM-generated entities into existing ErDiagram, with duplicate detection by relationship/query/mutation name
- break:
  - **`ErDiagram.configs` → `ErDiagram.entities`**: parameter renamed; all internal consumers updated

## v4.1

### v4.1.0 (2026-4-2)
- feat:
  - **MCP dependencies are now optional**: `fastmcp` moved from core dependencies to `[project.optional-dependencies]` under `mcp` group. Install via `pip install pydantic-resolve[mcp]`. Core functionality (Resolver, GraphQL, ERD) no longer pulls in `fastmcp`.
  - MCP imports in `pydantic_resolve/__init__.py` now use `try/except` for graceful degradation when `fastmcp` is not installed.
- fix:
  - Remove misleading `config_global_resolver` calls from MCP module docstring examples (`__init__.py`, `server.py`). MCP internally uses `config_resolver` via `GraphQLHandler` for proper isolation.

## v4.0

### v4.0.1 (2026-4-1)
- fix:
  - **Auto-added FK fields no longer leak into GraphQL response**: `ResponseBuilder._add_fk_fields()` now uses `Field(exclude=True)` instead of `...`, so fields like `id` that are auto-added for `AutoLoad` resolution are excluded from `model_dump()` serialization while remaining accessible as attributes
  - **Support scalar target relationships in GraphQL**: `_build_relationship_field()` now handles scalar targets (e.g., `str`, `int`) via `_is_scalar_relationship()` check, skipping recursive model building for non-BaseModel targets
  - **Allow scalar relationship fields without sub-selections**: `_add_relationship_fields()` now permits scalar relationship fields to be included even when no sub-fields are selected

### v4.0.0 (2026-3-29)

**BREAKING CHANGES** — ER Diagram API overhaul, simplified Relationship definition. See [Migration Guide](./migration.md) for details.

- feat:
  - **`Relationship` parameter renames**: `field` → `fk`, `target_kls` → `target`
  - **`Relationship.name` replaces `default_field_name`**: each Relationship must declare a unique `name`, used as GraphQL field name and AutoLoad lookup key
  - **`Relationship.fk_fn` replaces `field_fn`**
  - **`Relationship.fk_none_default` / `fk_none_default_factory` replace `field_none_default` / `field_none_default_factory`**
  - **`AutoLoad` replaces `LoadBy`**: AutoLoad no longer requires FK field name; uses `origin` parameter to match by relationship name, defaults to field name
  - **Remove `MultipleRelationship` and `Link`**: multiple relationships to the same target are now separate `Relationship` entries with independent `name`
  - **Remove deprecated `Resolver` parameters**: `loader_filters` and `global_loader_filter` (deprecated since v1.9.3) are removed; use `loader_params` and `global_loader_param`
  - **`_resolve_ref` searches registered entities**: when module attribute lookup fails, falls back to searching registered entity list, resolving same-module class ordering issues

- refactor:
  - `ResponseBuilder` removes `RelationshipInfo` wrapper, uses `Relationship` directly
  - `DefineSubset` modifier logic extracted into `_apply_config_modifiers_to_field`
  - `DefineSubset` auto-adds missing AutoLoad FK fields with `exclude=True`
  - SDL / Introspection generators unified on `rel.name` and `rel.target`, all `MultipleRelationship` branches removed
  - Removed `__pydantic_resolve_relationships__` attribute name; use `__relationships__` only
  - Added type compatibility check in `ErLoaderPreGenerator.prepare()` for early mismatch detection

## v3.3

### 3.3.0 (2026-3-27)
- feat:
  - migrate from mcp to fastmcp ver 3


## v3.2

### v3.2.3 (2026-3-24)
- feat:
  - **GraphQL hides relationship fields without loaders**: `Relationship` fields with `loader=None` are now hidden from GraphQL SDL and introspection, preventing runtime errors when querying unresolvable fields
  - Applies to both `SDLBuilder` and `IntrospectionGenerator`
- test:
  - Add `TestHideRelationshipsWithoutLoader` test class in `tests/graphql/test_sdl_builder.py`

### v3.2.2 (2026-3-23)
- fix:
  - **GraphQL datetime serialization**: Changed `model_dump(by_alias=True)` to `model_dump(mode='json', by_alias=True)` in executor to ensure datetime, date, time, Decimal, and other non-JSON types are properly serialized to JSON-compatible formats
  - Before: `TypeError: Object of type datetime is not JSON serializable`
  - After: datetime fields are automatically serialized to ISO-8601 strings
- test:
  - Add `tests/graphql/test_datetime_support.py` for datetime, date, time, Decimal serialization

### v3.2.1 (2026-3-22)
- fix:
  - **GraphQL introspection now includes `Relationship.target_kls` types**: `IntrospectionGenerator._collect_all_types` now collects types from `Relationship.target_kls` when the target type is not explicitly registered in `er_diagram.configs`, ensuring consistency with SDL generation
  - Before: Introspection types list was missing types referenced in relationships, causing field type references to point to undefined types
  - After: Both SDL and introspection include the same types, field type references are always valid
- test:
  - Add `tests/graphql/test_missing_target_type.py` for introspection/SDL consistency
  - Add `tests/graphql/test_forward_ref_resolution.py` for string reference resolution in `__relationships__`


### v3.2.0 (2026-3-19)
- feat:
  - **DataLoader context injection**: Class-type DataLoaders can now declare a `_context` attribute to access Resolver's global context
  - Early validation: Raises `LoaderContextNotProvidedError` if a DataLoader requires context but Resolver doesn't provide one
  - Useful for permission filtering scenarios where `user_id` needs to be passed to loaders
  - Example:
    ```python
    class UserLoader(DataLoader):
        _context: dict  # Declare context requirement

        async def batch_load_fn(self, keys):
            user_id = self._context.get('user_id')
            # Use user_id for permission filtering
            ...

    # Resolver automatically injects context
    resolver = Resolver(context={'user_id': 123})
    ```

## v3.1

### v3.1.1 (2026-3-18)
- feat:
    - **Auto-add missing AutoLoad FK fields in DefineSubset**: When using `AutoLoad` annotation in `DefineSubset`, the referenced FK field (e.g., `user_id` in `AutoLoad('user_id')`) is now automatically added with `exclude=True` if not explicitly defined in the subset
    - **Early validation for invalid FK references**: If `AutoLoad` references a field that doesn't exist in the parent class, a `ValueError` is raised at class definition time instead of during `resolve()`

### v3.1.0 (2026-3-16)
- feature:
    - add MCP support based on ER diagram, add query/mutation decorator

## v3.0

### v3.0.7 (2026-3-5)
- perf:
  - **Two-level METADATA_CACHE with resolver_class isolation**: Cache structure changed from `METADATA_CACHE[root_class]` to `METADATA_CACHE[id(resolver_class)][root_class]`, isolating caches for different resolver configurations (created via `config_resolver`)
  - **Pre-analysis in ResponseBuilder**: Dynamic response models are now pre-analyzed immediately after creation in `ResponseBuilder._create_model()`, avoiding repeated analysis in `Resolver.resolve()`
  - **Concurrent query execution in GraphQL executor**: Moved `query_method` execution from Phase 1 (serial) to Phase 2 (concurrent), enabling parallel I/O operations for multiple root queries
  - Before: Phase 1 executes query_methods serially → Phase 2 resolves concurrently
  - After: Phase 1 builds models only → Phase 2 executes (query_method + transform + resolve) concurrently

### v3.0.6 (2026-3-3)
- feat:
  - **GraphQL schema now includes `Relationship.target_kls` types**: Pydantic types referenced in relationships are automatically collected and generated as GraphQL types, even if not explicitly registered in `er_diagram.configs`
  - Supports `Relationship` with `list[T]` generics and `load_many=True`

### v3.0.5 (2026-3-2)
- feat:
  - **Enum support for GraphQL**: Full enum type support across SDL generation, introspection, query execution, and mutation input
  - Enum fields now serialize to enum name (e.g., `"ADMIN"`) conforming to GraphQL convention
  - Enum default values in introspection formatted correctly (e.g., `"USER"` instead of `"UserRole.USER"`)
  - Mutation arguments accept enum names and convert to Python enum members
- refactor:
  - **Enum serialization optimization**: Replaced recursive `_convert_enum_to_name` post-processing with Pydantic `PlainSerializer` for better performance
  - Extracted `_add_enum_definitions()` helper in SDL generator to reduce code duplication
  - Fixed `_format_default_value()` return type and moved Enum import to module level in introspection generator
  - Added enum handling in `_map_python_type_to_gql_for_input()` for input types

### v3.0.4 (2026-3-1)
- feat:
  - add LRU cache for GraphQL response model generation in `ResponseBuilder`
  - `FieldSelection` now implements `__hash__` and `__eq__` to support caching (arguments excluded from comparison)
  - same query structure with different arguments will hit cache, improving performance
  - cache size: 256 entries with LRU eviction

### v3.0.3 (2026-3-1)
- refactor:
  - `GraphQLHandler` now creates diagram-specific resolver internally using `config_resolver`, removing `resolver_class` parameter
  - ensures `AutoLoad` annotations work without requiring `config_global_resolver()` to be called
  - convert all relative imports to absolute imports in `pydantic_resolve/` directory

### v3.0.2 (2026-3-1)
- fix:
  - fix introspection for scalar return types (bool, int, float, str) in mutations

### v3.0.1 (2026-2-28)
- refactor:
  - graphql interface

### v3.0.0 (2026-2-27)

- add support for auto-generating graphql interface for ERD.

## v2.5

### v2.5.0 (2026-2-21)

- stable release

### v2.5.0alpha2

- refactor:
  - **serialization decorator**: Use `json_schema_extra` mechanism instead of monkey-patching
    - Collects all nested Pydantic types at decoration time via `_collect_nested_types`
    - Sets `json_schema_extra` on root class and all nested types automatically
    - Respects existing configurations (skips types that already have `json_schema_extra`)
    - Removes ~100 lines of code (`_process_schema`, `_process_nested_type`, `_process_reference`)
    - File: `pydantic_resolve/utils/openapi.py`

### v2.5.0alpha1

- feat:
  - **NEW**: `@serialization` decorator for recursive JSON schema processing
    - No-parameter decorator, use `@serialization` directly
    - Example:
      ```python
      @serialization
      class Person(BaseModel):
          name: str = ''
          address: Address | None = None

      schema = Person.model_json_schema(mode='serialization')
      # All nested models (Address) will have required fields set correctly
      ```

### v2.5.0alpha

- test:
  - Add edge case tests for Pydantic model resolution and collector handling
    - Empty classes, missing fields, collector validation, expose conflicts
    - Self-reference and circular reference handling
    - Inheritance chain testing
    - File: `tests/analysis/test_analysis_edge_cases.py`

- refactor:
  - **loader management**: Enhance loader classes and validation with new architecture
    - Improved loader instance creation and validation
    - Better error messages for missing or invalid loader configurations
    - File: `pydantic_resolve/loader_manager.py`

  - **ContextVar optimization**: Optimize ancestor and collector management
    - Use single dict-based ContextVar instead of multiple ContextVars
    - Reduces context variable overhead from N+1 to 1 per category
    - Pre-create parent ContextVar to avoid repeated creation
    - File: `pydantic_resolve/resolver.py`

- doc:
  - Add Entity-First architecture discussion
    - Comprehensive documentation on Entity-First design pattern
    - Examples of data assembly with automatic resolver
    - GraphQL-inspired concepts for FastAPI + Pydantic
    - Files:
      - `docs/fastapi-pydantic-architecture-outline.md`
      - `docs/fastapi-pydantic-architecture-outline.en.md`

  - Update README with detailed Pydantic response schemas and examples
  - Clarify ORM and Pydantic schema relationship


## v2.4

### v2.4.7 (2026-1-29)

- refactor:
    - use modern type annotation
    - logger
    - analysis.py for better readibility
    - improve doc, add more details about ErDiagram
   

### v2.4.6 (2026-1-28)
