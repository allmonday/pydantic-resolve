# Changelog

- **Major (X.0.0)**: Major new features or breaking changes
- **Minor (x.Y.0)**: New features, backward compatible
- **Patch (x.y.Z)**: Bug fixes and minor improvements

## 5.10

### 5.10.0 (2026-6-19)

Introduces a **GraphQL surface for UseCase services** — a way to compose multiple `UseCaseService` methods in a single GraphQL query, plus the schema/introspection machinery that goes with it. MCP is one consumer of this surface (the AI-agent packaging), but the underlying Python APIs (`UseCaseResources.compose`, `compose_introspect`, `build_compose_schema`) work directly from FastAPI or any HTTP framework. See `demo/use_case/app_compose.py` for a non-MCP HTTP example.

The classic 4-tool UseCase MCP server (`create_use_case_mcp_server` / `list_services` / `describe_service` / `call_use_case`) is removed; the GraphQL compose MCP server (`create_use_case_graphql_mcp_server`) is now the single MCP entry point. graphql-core's role in this codebase narrows to query parsing — type representation, schema construction, and introspection execution all switch to the existing ErDiagram type infrastructure (`TypeMapper` + `TypeInfo` registry).

- feat:
  - **UseCase GraphQL compose** (`UseCaseResources.compose(query, context)`): execute a fixed 3-level GraphQL query — root → Service → Method → DTO field selection — and return a nested `{service: {method: result}}` dict. Each `@query` method runs concurrently via `asyncio.gather`; `@mutation` methods run serially in declaration order. Field selection projects each method's return DTO via `build_subset_model` before serialization. `Resolver` / `AutoLoad` on returned DTOs fire normally — business methods are responsible for resolving their own outputs.
  - **UseCase GraphQL introspection** (`compose_introspect(app, query)`): GraphiQL-compatible `__schema` / `__type(name: "...")` / `__typename` queries against the app's cached schema registry. Standard 5 built-in directives (`skip` / `include` / `deprecated` / `specifiedBy` / `oneOf`) reported. Walks a hand-built `{type_name: TypeInfo}` registry instead of going through graphql-core.
  - **`build_compose_schema(app)`**: walks UseCaseService classes once at registration time, producing the `{type_name: TypeInfo}` registry (services as `{Service}Query` OBJECT, every reachable DTO + Enum, plus the 5 standard GraphQL scalars). Cached on `UseCaseResources.compose_schema` so introspection and SDL rendering don't rebuild per call.
  - **`FromContext` marker** + per-app `context_extractor`: `Annotated[int, FromContext()]` parameters are server-injected (e.g. user identity extracted from the Authorization header), not settable from query args. Same service method works unchanged across FastAPI (`Depends(get_current_user)`) and MCP (`context_extractor`).
  - **`create_use_case_graphql_mcp_server(apps)`**: MCP packaging of the above. 4-layer progressive disclosure — `list_apps` → `describe_compose_schema` (service + method listing) → `describe_compose_method` (args / returns / focused SDL showing every reachable DTO and Enum) → `compose_query` (data execution). Pure wrapper around the Python APIs; no MCP-specific business logic.
  - **Spec-compliant SDL rendering**: type descriptions above `type X {`, field descriptions above each field, both as block strings (`"""..."""`). Enum types referenced by a method's return DTO appear in SDL alongside OBJECT types. See `method_sdl(registry, service, method)`.

- refactor:
  - **graphql-core scope narrowed to query parsing only**. Removed `pydantic_resolve/graphql/type_converter.py` (236 lines) — its `pydantic_to_graphql_type` is fully replaced by `TypeMapper.map_to_graphql_type` from the ErDiagram path. The two paths now share one type system instead of running parallel implementations.
  - **Classic MCP server removed** (pre-release on a feature branch, no breaking change for downstream users). Drops `pydantic_resolve/use_case/server.py` (480 lines) and `demo/use_case/mcp_server.py` + `mcp_server_with_context.py`.
  - **`introspector.py` removed** (646 lines): never called from the production path; `mcp_server` + `compose_schema` already cover the same surface via different code paths.
  - **Shared utilities consolidated**:
    - `TypeMapper.collect_referenced_types(annotation, *, include_enums=True)` — single canonical walker for "find every BaseModel/Enum reachable from this annotation". `TypeCollector.collect_nested_pydantic_types` and `utils/openapi._collect_nested_types` become thin wrappers.
    - `utils/field_metadata.iter_fields_with_marker(model_cls, marker_cls)` — centralizes the `ExposeAs` / `SendTo` / `AutoLoad` field-scan pattern.
    - `GraphQLTypeInfo.leaf_name` property — walks NON_NULL / LIST wrappers to the named leaf.
    - `business.iter_use_case_methods(cls, *, enable_mutation=True)` — collapses the `getattr + kind-filter` pattern duplicated across compose_schema and mcp_server.
    - `context.is_from_context_annotation` — consolidates 4 inline copies.

- fix:
  - **Root Query service fields point at the right OBJECT**: previously degraded to a scalar fallback (`String` / `Int`) because TypeMapper didn't recognize `UseCaseService` subclasses. Now correctly renders `NON_NULL(OBJECT({Service}Query))`.
  - **GraphQL duplicate fields rejected** instead of silently merged (affects `QueryParser`).
  - **`defaultValue` uses `json.dumps`** instead of `repr` so booleans serialize as `true` / `false` (not `True` / `False`) and strings use double quotes per GraphQL spec.

- docs:
  - `docs/use_case_mcp_service.md` + `.zh.md` rewritten for the compose server (4-layer walkthrough, FromContext + context_extractor pattern, SDL examples).
  - `docs/api_use_case_mcp.md` + `.zh.md` document only `create_use_case_graphql_mcp_server`.
  - `demo/use_case/services.py` enriched with class docstrings + `Field(description=...)` + a `TaskStatus` Enum so the SDL output is meaningful end-to-end.

## 5.8

### 5.8.0 (2026-6-8)

- feat:
  - **BFS execution mode for Resolver**: replace recursive DFS traversal with level-by-level BFS. All `resolve_*` methods at the same level run concurrently via `asyncio.gather`, maximizing DataLoader batch sizes. Two-phase design: Phase A resolves top-down, Phase B executes `post_*` bottom-up
- perf:
  - **DataLoader batch efficiency**: same-level resolves now share a single gather call, significantly increasing DataLoader batch coalescing. SQLite P50 comparison (DFS → BFS):

    Medium (20 users, 10 sprints, 200 tasks)

    | Scenario           | DFS (ms) | BFS (ms) | Delta  |
    |--------------------|----------|----------|--------|
    | Q1: 1-level        | 5.57     | 3.71     | -33.4% |
    | Q2: 2-level        | 6.28     | 4.42     | -29.6% |
    | Q3: 3-level linear | 5.90     | 4.08     | -30.8% |
    | Q4: wide parallel  | 8.32     | 5.96     | -28.4% |

    Large (50 users, 20 sprints, 1000 tasks)

    | Scenario           | DFS (ms) | BFS (ms) | Delta  |
    |--------------------|----------|----------|--------|
    | Q1: 1-level        | 25.15    | 15.53    | -38.3% |
    | Q2: 2-level        | 26.57    | 16.88    | -36.5% |
    | Q3: 3-level linear | 13.04    | 8.37     | -35.8% |
    | Q4: wide parallel  | 19.35    | 12.92    | -33.2% |

    XLarge (200 users, 50 sprints, 2500 tasks)

    | Scenario           | DFS (ms) | BFS (ms) | Delta  |
    |--------------------|----------|----------|--------|
    | Q1: 1-level        | 95.62    | 63.25    | -33.9% |
    | Q2: 2-level        | 97.75    | 66.94    | -31.5% |
    | Q3: 3-level linear | 77.77    | 31.11    | -60.0% |
    | Q4: wide parallel  | 107.49   | 73.18    | -31.9% |

- fix:
  - **`post_default_handler` ordering**: now runs after all named `post_*` methods complete at the same level, ensuring consistent data visibility
  - **`expose_to_descendant` timing**: child ancestor context is now built after all resolves at a level finish, so `resolve_` methods that set expose fields are visible to children
  - **Debug/profile mode**: restore timing data collection in BFS traversal
- refactor:
  - Remove DFS recursive traversal and ContextVar infrastructure (~379 lines)
  - Replace bare tuple with `_ResolveJob` dataclass for resolve job representation
  - Extract `_traverse` into `_phase_a_resolve`, `_phase_b_prepare_collectors`, `_phase_b_execute_posts` for readability
- docs:
  - Redesign landing page with Clean Architecture emphasis
  - Improve quick start, post-processing, UseCase MCP, and Voyager guides
  - Update README with before/after comparison and advanced examples

## 5.9

### 5.9.0 (2026-6-9)

- perf:
  - **BFS resolver hot path optimization**: reduce per-node overhead across all BFS phases. Benchmark comparison (5.8.0 → 5.8.1, pytest-benchmark, mean time):

    | Scenario                        | 5.8.0 (ms) | 5.8.1 (ms) | Delta   |
    |---------------------------------|------------|------------|---------|
    | very_large_dataset              | 53.75      | 45.68      | -15.0%  |
    | large_dataset_simple_objects    | 29.02      | 22.56      | -22.3%  |
    | large_dataset_with_post         | 20.28      | 17.19      | -15.2%  |
    | expose_three_levels             | 25.10      | 21.72      | -13.5%  |
    | deep_nesting_standard           | 14.92      | 13.85      | -7.2%   |
    | dataloader                      | 27.67      | 27.41      | -0.9%   |

  - Optimizations applied:
    - `setattr` → `object.__setattr__` to bypass pydantic validation on already-validated values
    - `copy.deepcopy` → lightweight `_clone_collector` for collector cloning in Phase B
    - `isinstance` fast path in `try_parse_data_to_target_field_type` to skip redundant `validate_python`
    - Cache `kls_path` from metadata instead of repeated f-string construction
    - Inline metadata lookups, eliminating per-node function call overhead and intermediate allocation

## 5.7

### 5.7.0 (2026-5-21)

- feat:
  - **UseCase MCP selection projection for `call_use_case`**: `call_use_case` now supports response field selection so clients can request focused subsets of nested result data instead of always receiving the full payload
  - **Selection metadata in service introspection**: UseCase MCP introspection now exposes selection-aware response information, helping MCP clients discover which fields can be projected
- docs:
  - Update English and Chinese UseCase MCP docs with selection projection examples and guidance
- test:
  - Add coverage for selection projection behavior across UseCase MCP responses

## 5.6

### 5.6.3 (2026-5-21)

- fix:
  - **UseCase MCP fallback type-hint resolution**: unresolved return forward references no longer break runtime parameter coercion or `FromContext` injection in `call_use_case`, so execution now stays consistent with `describe_service`
- refactor:
  - **Shared type-hint resolution helpers**: move use_case fallback annotation resolution into `utils/types.py` and reuse it across introspection, runtime coercion, and return annotation extraction

### 5.6.2 (2026-5-20)

- fix:
  - **UseCase MCP type coercion for `call_use_case`**: arguments received from MCP clients (JSON-native types like `int` passed where `str` is expected) are now coerced to the correct Python type using Pydantic `TypeAdapter` before being passed to the underlying method

### 5.6.1 (2026-5-20)

- fix:
  - **UseCase MCP FromContext parameters are described as optional**: parameters annotated with `Annotated[..., FromContext()]` now appear as optional in generated `describe_service` signatures and parameter metadata, so MCP clients do not need to provide values that are injected from context

### 5.6.0 (2026-5-9)

This release introduces breaking changes to the UseCaseService API. Methods must now be decorated with `@query` or `@mutation` instead of using `@classmethod`.

- feat:
  - **`@query` / `@mutation` decorators for UseCaseService**: UseCaseService methods now use `@query` and `@mutation` decorators (from `pydantic_resolve`) instead of `@classmethod`. The decorators reuse the same implementation as GraphQL, automatically converting methods to classmethods and setting metadata
  - **`enable_mutation` app-level control**: New `UseCaseAppConfig(enable_mutation=False)` option to hide mutation methods from MCP tools. When disabled, `list_services` excludes mutations from count, `describe_service` omits mutation methods, and `call_use_case` blocks mutation calls
  - **`kind` field in `describe_service`**: Each method in `describe_service` response now includes a `kind` field (`"query"` or `"mutation"`) for AI agents to distinguish read vs write operations
- break:
  - **UseCaseService methods require `@query` / `@mutation`**: Undecorated async classmethods are no longer automatically discovered by `BusinessMeta`. All existing UseCaseService subclasses must add `@query` or `@mutation` decorators
  - **`__use_case_methods__` structure changed**: value type changed from `classmethod` descriptor to `dict` with keys `method`, `kind`, `description`

## 5.5

### 5.5.0 (2026-5-9)

This release introduces breaking changes to the AutoLoad API. See [Migration Guide — v5.4 to v5.5](./migration.md#v54-to-v55) for upgrade instructions.

- feat:
  - **Implicit AutoLoad**: fields whose names match a relationship `name` in the ER Diagram are automatically resolved without requiring `Annotated[..., AutoLoad()]` annotation. Explicit `AutoLoad(origin=...)` is still needed when the field name differs from the relationship name
  - **Standalone `AutoLoad` function**: `AutoLoad` is now a module-level function (`from pydantic_resolve import AutoLoad`) instead of a factory created via `diagram.create_auto_load()`. No diagram binding required
  - **Ambiguity detection for external ErDiagram**: when multiple `ErDiagram` instances register conflicting relationships (same name, different FK) for the same entity class, `DefineSubset` raises `ValueError` at class-definition time instead of silently using the last registration
- break:
  - **`ErDiagram.create_auto_load()` removed**: replaced by standalone `AutoLoad()` function. See [Migration Guide](./migration.md) for details
  - **`LoaderInfo._er_configs_map` removed**: no longer used; relationship lookup now goes through MRO + global registry
- refactor:
  - `ErLoaderPreGenerator.prepare()` restructured into Phase 1 (explicit AutoLoad) and Phase 2 (implicit matching by field name), consistent with `DefineSubset` FK injection logic
  - `DefineSubset` FK auto-injection unified via `_collect_relationship_candidates_from_mro` + `_select_relationship`, removing direct dependency on `LoaderInfo._er_configs_map`
  - `ResponseBuilder` uses implicit AutoLoad for dynamic GraphQL response models, removing `Annotated[..., AutoLoad()]` wrapping
  - `ErDiagram` registration changed from overwrite (`kls -> Entity`) to append (`kls -> [Entity]`) to support ambiguity detection

## 5.4

### 5.4.0 (2026-5-8)

- feat:
  - **UseCase MCP server**: multi-app management MCP server that exposes UseCaseService methods to AI agents via progressive disclosure (list_apps → list_services → describe_service → call_use_case)
  - **UseCase `FromContext` annotation**: methods can declare parameters annotated with `FromContext` to receive values from request context, with `context_extractor` support for async extraction
  - **`get_return_annotation()` utility**: extract return type annotation from methods (handles classmethod, `__future__` annotations, string fallback) for convenient FastAPI `response_model` usage
- refactor:
  - Update TypeMapper and SDLBuilder to use new mapping methods and improve type resolution
  - Remove unused method for collecting types from method parameters
  - Consolidate type checking in `introspector.py` to use shared utilities from `utils/types.py` (`_is_list`, `_is_optional`, `get_core_types`), eliminating duplicate type-handling code
  - Simplify `_collect_dto_types` with `get_core_types` for one-pass type unwrapping

## 5.3

### 5.3.1 (2026-4-22)

- bug:
  - fix pagination in many to many relationship

### 5.3.0 (2026-4-22)

- feat:
  - **GraphQL limit/offset pagination**: `GraphQLHandler(enable_pagination=True)` enables server-side pagination for one-to-many relationships. Requires `page_loader` and `order_by` configured on `Relationship`. Supports multi-level nested pagination with independent limit/offset per field
  - **`Resolver(resolved_hooks=...)` dependency injection**: core Resolver now accepts a list of post-resolve hooks via constructor, decoupling GraphQL-specific pagination logic from the core resolution engine
- refactor:
  - Extract `inject_nested_pagination` into standalone `graphql/pagination/injector.py` module, injected via `resolved_hooks` instead of hardcoded in core `Resolver`
  - Consolidate pagination hidden field names into `constant.py` (`GRAPHQL_PAGINATION_FIELD_PREFIX`, `GRAPHQL_PAGINATION_TREE_FIELD`)
  

## 5.2

### 5.2.0 (2026-4-18)

- feat:
  - **`Resolver(split_loader_by_type=True)`**: create separate DataLoader instances per request_type so lightweight views (e.g. `TaskCard` with 2 columns) don't query all columns needed by heavyweight views (e.g. `TaskDetail` with 20 columns). Incompatible with `loader_instances`. See [Resolver API](./api_resolver.md) for details.
- refactor:
  - Improved `validate_and_create_loader_instance` readability with unified split/non-split logic
  - Deterministic `_query_meta` output order

## 5.1

### 5.1.0 (2026-4-13)

- feat:
  - **Request context support for GraphQL**: `handler.execute()` accepts an optional `context` dict, passed into `@query`/`@mutation` methods via `_context` parameter and forwarded to the internal `Resolver(context=...)` for DataLoader context injection
  - **`_context` parameter in `@query`/`@mutation` methods**: declare `_context: dict` in method signature to receive request-scoped data (e.g. `user_id` from JWT); the parameter is hidden from GraphQL schema — clients cannot see or set it
  - **`_context` excluded from SDL and introspection**: `SDLBuilder` and `IntrospectionGenerator` skip `_context` when generating query/mutation field arguments
  - **`AppConfig.context_extractor` for MCP**: optional callback `(Context) -> dict | Awaitable[dict]` that extracts request-scoped context from FastMCP HTTP request (e.g. user identity from Authorization header), passed as `context=` to `handler.execute()`
  - **RBAC/ABAC demo**: new `demo/rbac/` showcasing multi-level permission queries with DataLoader batching, FK-based ancestor tracing, ABAC condition evaluation, and mail group permission inheritance
- refactor:
  - Entity classes updated for context handling in GraphQL API

## 5.0

### 5.0.1 (2026-4-11)

- fix:
  - fix minor type issues

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
  - **`Mapping` descriptor** (`integration.mapping`): unified ORM-to-DTO mapping descriptor
  - **`ErDiagram.add_relationship()`**: merge ORM-generated entities into existing ErDiagram, with duplicate detection by relationship/query/mutation name
  - **Built-in GraphiQL page helper**: export `get_graphiql_html()` from `pydantic_resolve.graphql` and add `GraphQLHandler.get_graphiql_html()` for serving a ready-to-use GraphiQL IDE alongside the GraphQL endpoint
  - **MCP full-schema tool**: multi-app MCP servers now expose `get_full_schema(app_name, response_type='sdl'|'introspection')` to fetch the entire schema in one call
  - **ORM-first GraphQL response validation**: dynamic response models now preserve entity `from_attributes=True` or enable it via `enable_from_attribute_in_type_adapter`, and relationship fields use a synthetic `validation_alias` to avoid premature lazy-loading of ORM relationships before `AutoLoad` runs
  - **Forward-ref module path syntax**: `base_entity()` now resolves relationship targets written as `'package.module:ClassName'` and `list['package.module:ClassName']`, reducing same-module ordering constraints
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
