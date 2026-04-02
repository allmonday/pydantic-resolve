from dataclasses import dataclass
from typing import Iterator, Any, Callable, Optional
from pydantic import BaseModel, model_validator, Field
import logging
import importlib
import functools
import pydantic_resolve.constant as const
from pydantic_resolve.utils import class_util, types
from pydantic_resolve.utils.depend import Loader

logger = logging.getLogger(__name__)


class QueryConfig(BaseModel):
    """Query method configuration for defining Query methods outside Entity and binding dynamically."""
    method: Callable
    name: Optional[str] = None
    description: Optional[str] = None


class MutationConfig(BaseModel):
    """Mutation method configuration for defining Mutation methods outside Entity and binding dynamically."""
    method: Callable
    name: Optional[str] = None
    description: Optional[str] = None


class Relationship(BaseModel):
    fk: str  # FK field name on this entity
    target: Any  # Target entity class
    name: str  # Relationship name (unique identifier, becomes GraphQL field name)

    # Loader and behavior:
    loader: Callable | None = None
    fk_fn: Callable | None = None
    fk_none_default: Any | None = None
    fk_none_default_factory: Callable[[], Any] | None = None
    load_many: bool = False
    load_many_fn: Callable[[Any], Any] | None = None

    @model_validator(mode="after")
    def _validate_defaults(self) -> "Relationship":
        fields_set = getattr(self, 'model_fields_set', set())
        val_set = 'fk_none_default' in fields_set
        factory_set = 'fk_none_default_factory' in fields_set
        if val_set and factory_set:
            raise ValueError(
                "fk_none_default and fk_none_default_factory cannot both be defined"
            )
        return self

class Entity(BaseModel):
    kls: type[BaseModel]
    relationships: list[Relationship] = Field(default_factory=list)
    queries: list[QueryConfig] = Field(default_factory=list)
    mutations: list[MutationConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_relationships(self) -> "Entity":
        rels = self.relationships or []

        # Disallow duplicate name
        seen = set()
        for r in rels:
            if r.name in seen:
                raise ValueError(
                    f"Duplicate name detected in {self.kls.__name__}: '{r.name}'"
                )
            seen.add(r.name)

        # Validate name conflicts with scalar/inherited fields
        self._validate_name_conflicts()

        return self

    def _validate_name_conflicts(self) -> None:
        """Detect naming conflicts for relationship name."""
        from typing import get_type_hints

        # 1. Collect scalar fields
        try:
            scalar_fields = set(get_type_hints(self.kls).keys())
        except Exception:
            scalar_fields = set()

        # 2. Check each relationship's name
        for rel in self.relationships or []:
            rel_name = rel.name

            # Check for conflicts with scalar fields
            if rel_name in scalar_fields:
                raise ValueError(
                    f"Name conflict in {self.kls.__name__}: '{rel_name}' - "
                    f"relationship name conflicts with scalar field. "
                    f"Relationship(fk={rel.fk}), target={rel.target}"
                )

        # 3. Check for conflicts with parent class fields
        for base_cls in self.kls.__mro__[1:]:  # Skip self
            if base_cls is object:
                continue
            try:
                base_fields = set(get_type_hints(base_cls).keys())
            except Exception:
                continue

            for rel in self.relationships or []:
                if rel.name in base_fields:
                    raise ValueError(
                        f"Name conflict in {self.kls.__name__}: '{rel.name}' - "
                        f"relationship name conflicts with inherited field from {base_cls.__name__}. "
                        f"Relationship(fk={rel.fk})"
                    )

class ErDiagram(BaseModel):
    configs: list[Entity]

    @model_validator(mode="after")
    def _validate_configs(self) -> "ErDiagram":
        cfgs = self.configs or []
        seen = set()
        seen_names = {}
        for cfg in cfgs:
            kls = cfg.kls
            if kls in seen:
                raise ValueError(f"Duplicate config.kls detected: {kls}")
            seen.add(kls)

            # Check for duplicate class names (important for GraphQL integration)
            class_name = kls.__name__
            if class_name in seen_names:
                existing_module = seen_names[class_name].__module__
                current_module = kls.__module__
                raise ValueError(
                    f"Duplicate entity name '{class_name}' detected. "
                    f"Entity names must be unique for GraphQL schema generation. "
                    f"Conflict: {existing_module}.{class_name} vs {current_module}.{class_name}"
                )
            seen_names[class_name] = kls

        # Dynamically bind queries and mutations
        self._bind_query_mutation_methods()
        return self

    description: str | None = None

    def _bind_query_mutation_methods(self) -> None:
        """Dynamically bind methods from queries/mutations config to Entity classes.

        Uses a wrapper to automatically ignore the cls parameter, making user methods
        look like regular functions.

        Raises:
            ValueError: If a pydantic-resolve method with the same name already exists
                on the target class (defined via decorator)
        """
        for entity_cfg in self.configs:
            kls = entity_cfg.kls

            for query_cfg in entity_cfg.queries:
                method = query_cfg.method
                method_name = method.__name__

                # Conflict detection: check if a pydantic-resolve method with the same name exists
                # Only detect methods defined via decorator (with _pydantic_resolve_decorator marker)
                # Do not detect config-bound methods (allow re-binding for idempotency)
                if method_name in kls.__dict__:
                    existing = kls.__dict__[method_name]
                    func = getattr(existing, '__func__', existing)
                    # Check if the method is defined via decorator (not config-bound)
                    if hasattr(func, const.GRAPHQL_QUERY_ATTR) or hasattr(func, const.GRAPHQL_MUTATION_ATTR):
                        # If the method is from decorator, raise exception
                        if not hasattr(func, const.GRAPHQL_CONFIG_BOUND_ATTR):
                            raise ValueError(
                                f"Method '{method_name}' already exists in {kls.__name__} "
                                f"(defined via @query/@mutation decorator). "
                                f"Cannot bind QueryConfig method with the same name. "
                                f"Use either decorator OR QueryConfig, not both."
                            )

                # Create wrapper that automatically ignores cls parameter
                @functools.wraps(method)
                def query_wrapper(cls, *args, _method=method, **kwargs):
                    return _method(*args, **kwargs)

                # Set metadata (consistent with @query decorator)
                setattr(query_wrapper, const.GRAPHQL_QUERY_ATTR, True)
                setattr(query_wrapper, const.GRAPHQL_QUERY_NAME_ATTR, query_cfg.name)
                setattr(query_wrapper, const.GRAPHQL_QUERY_DESCRIPTION_ATTR, query_cfg.description)
                setattr(query_wrapper, const.GRAPHQL_CONFIG_BOUND_ATTR, True)  # Mark as config-bound

                # Bind as classmethod
                setattr(kls, method_name, classmethod(query_wrapper))

            for mutation_cfg in entity_cfg.mutations:
                method = mutation_cfg.method
                method_name = method.__name__

                # Conflict detection: check if a pydantic-resolve method with the same name exists
                if method_name in kls.__dict__:
                    existing = kls.__dict__[method_name]
                    func = getattr(existing, '__func__', existing)
                    if hasattr(func, const.GRAPHQL_QUERY_ATTR) or hasattr(func, const.GRAPHQL_MUTATION_ATTR):
                        if not hasattr(func, const.GRAPHQL_CONFIG_BOUND_ATTR):
                            raise ValueError(
                                f"Method '{method_name}' already exists in {kls.__name__} "
                                f"(defined via @query/@mutation decorator). "
                                f"Cannot bind MutationConfig method with the same name. "
                                f"Use either decorator OR MutationConfig, not both."
                            )

                # Create wrapper that automatically ignores cls parameter
                @functools.wraps(method)
                def mutation_wrapper(cls, *args, _method=method, **kwargs):
                    return _method(*args, **kwargs)

                # Set metadata (consistent with @mutation decorator)
                setattr(mutation_wrapper, const.GRAPHQL_MUTATION_ATTR, True)
                setattr(mutation_wrapper, const.GRAPHQL_MUTATION_NAME_ATTR, mutation_cfg.name)
                setattr(mutation_wrapper, const.GRAPHQL_MUTATION_DESCRIPTION_ATTR, mutation_cfg.description)
                setattr(mutation_wrapper, const.GRAPHQL_CONFIG_BOUND_ATTR, True)  # Mark as config-bound

                # Bind as classmethod
                setattr(kls, method_name, classmethod(mutation_wrapper))

    def create_auto_load(self):
        """Create an AutoLoad factory bound to this diagram's relationships.

        Returns a callable that creates LoaderInfo instances with embedded
        entity/relationship data.

        Usage:
            AutoLoad = diagram.create_auto_load()

            class MyResponse(Biz):
                user: Annotated[Optional[User], AutoLoad()] = None
        """
        er_configs_map = {config.kls: config for config in self.configs}

        def _auto_load(origin: str | None = None) -> LoaderInfo:
            return LoaderInfo(origin=origin, _er_configs_map=er_configs_map)

        return _auto_load

    def add_relationship(self, entities: list[Entity]) -> "ErDiagram":
        """Return a new ErDiagram with entities merged by class.

        Merge rules for entities with same `kls`:
        - relationships: merged by `name` (error on duplicate)
        - queries: merged by method name (error on duplicate)
        - mutations: merged by method name (error on duplicate)
        """
        if not entities:
            return ErDiagram(configs=list(self.configs), description=self.description)

        seen_incoming = set()
        for entity in entities:
            if entity.kls in seen_incoming:
                raise ValueError(f"Duplicate incoming entity.kls detected: {entity.kls}")
            seen_incoming.add(entity.kls)

        incoming_map = {entity.kls: entity for entity in entities}

        def _merge_method_configs(
            existing_items: list[QueryConfig] | list[MutationConfig],
            incoming_items: list[QueryConfig] | list[MutationConfig],
            *,
            kind: str,
            kls: type,
        ) -> list[QueryConfig] | list[MutationConfig]:
            merged = list(existing_items)
            seen_method_names = {cfg.method.__name__ for cfg in existing_items}

            for cfg in incoming_items:
                method_name = cfg.method.__name__
                if method_name in seen_method_names:
                    raise ValueError(
                        f"Duplicate {kind} method detected in {kls.__name__}: '{method_name}'"
                    )
                merged.append(cfg)
                seen_method_names.add(method_name)

            return merged

        merged_configs: list[Entity] = []
        existing_kls = {cfg.kls for cfg in self.configs}

        for cfg in self.configs:
            incoming = incoming_map.get(cfg.kls)
            if incoming is None:
                merged_configs.append(cfg)
                continue

            merged_relationships = list(cfg.relationships)
            seen_relationship_names = {rel.name for rel in merged_relationships}
            for rel in incoming.relationships:
                if rel.name in seen_relationship_names:
                    raise ValueError(
                        f"Duplicate relationship name detected in {cfg.kls.__name__}: '{rel.name}'"
                    )
                merged_relationships.append(rel)
                seen_relationship_names.add(rel.name)

            merged_queries = _merge_method_configs(
                cfg.queries,
                incoming.queries,
                kind='query',
                kls=cfg.kls,
            )
            merged_mutations = _merge_method_configs(
                cfg.mutations,
                incoming.mutations,
                kind='mutation',
                kls=cfg.kls,
            )

            merged_configs.append(
                Entity(
                    kls=cfg.kls,
                    relationships=merged_relationships,
                    queries=merged_queries,
                    mutations=merged_mutations,
                )
            )

        for incoming in entities:
            if incoming.kls not in existing_kls:
                merged_configs.append(incoming)

        return ErDiagram(configs=merged_configs, description=self.description)


class BaseEntity:  # just type (TODO: optimize)
    entities: list[Entity]
    def get_diagram() -> ErDiagram:
        raise NotImplementedError


@dataclass
class LoaderInfo:
    """Marker annotation - field name from annotation identifies the relationship."""
    origin: str | None = None
    _er_configs_map: dict | None = None  # {type: Entity}, set by create_auto_load()


def base_entity() -> type[BaseEntity]:
    """
    Creates a base class similar to SQLAlchemy's declarative_base().
    All classes inheriting from the returned Base class will be collected in Base.entities.

    CAUTION: make sure to import modules defining entities before calling Base.get_diagram()

    ```python
    from service.base import BaseEntity
    import service.a.schema
    import service.b.schema

    BaseEntity.get_diagram()
    ```
    """
    import sys
    from types import GenericAlias

    entities: list[Entity] = []
    inline_configs: list[tuple[type, Any]] = []

    def _resolve_ref(ref: Any, module_name: str) -> Any:
        """Resolve forward refs expressed as strings or list['Cls'] generics.

        Supports:
        - Simple class names: 'User' (looked up in module_name)
        - Module path syntax: 'path.to.module:ClassName' (lazy import from any module)
        - List generics: list['Foo'] or list['path.to.module:Foo']
        """
        if isinstance(ref, str):
            # Check for module path syntax (e.g., 'path.to.module:ClassName')
            if ':' in ref:
                module_path, class_name = ref.rsplit(':', 1)
                try:
                    mod = importlib.import_module(module_path)
                    if hasattr(mod, class_name):
                        return getattr(mod, class_name)
                    raise AttributeError(
                        f"Class '{class_name}' not found in module '{module_path}'"
                    )
                except ImportError as e:
                    raise ImportError(
                        f"Failed to import module '{module_path}' for reference '{ref}': {e}"
                    )

            # Fall back to original behavior - look up in the declaring module
            mod = sys.modules.get(module_name)
            if mod and hasattr(mod, ref):
                return getattr(mod, ref)

            # Try to find among registered entities (handles locally-defined classes)
            for entity_cls in entities:
                if entity_cls.__name__ == ref:
                    return entity_cls

            raise AttributeError(f"Unable to resolve reference '{ref}' in module '{module_name}'")

        if isinstance(ref, GenericAlias):  # e.g., list['Foo']
            args = ref.__args__
            if types._is_list(ref) and args:
                resolved_arg = _resolve_ref(args[0], module_name)
                return list[resolved_arg]
        return ref

    def get_diagram() -> ErDiagram:
        resolved_configs: list[Entity] = []
        for kls, rels in inline_configs:
            module_name = getattr(kls, '__module__', '')
            resolved_rels = []
            for rel in rels:
                resolved_rels.append(
                    rel.model_copy(update={
                        'target': _resolve_ref(rel.target, module_name),
                    })
                )

            resolved_configs.append(Entity(kls=kls, relationships=resolved_rels))
        return ErDiagram(configs=resolved_configs)

    class Base:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            # only register direct subclasses of Base, ignore inherited descendants
            if Base not in cls.__bases__:
                return

            entities.append(cls)
            # Check for inline relationships
            inline_rels = getattr(cls, const.ER_DIAGRAM_INLINE_RELATIONSHIPS, None)
            # Include entities even if they have empty relationships list
            # This is important for GraphQL @query methods on entities without relationships
            if inline_rels is not None:
                inline_configs.append((cls, inline_rels))

    # Attach the entities list and diagram to the Base class
    Base.entities = entities
    Base.get_diagram = get_diagram
    return Base


class ErLoaderPreGenerator:
    def __init__(self, er_diagram: ErDiagram | None) -> None:
        self.er_configs_map = {config.kls: config for config in er_diagram.configs} if er_diagram else None

    def _identify_entity(self, target: type) -> Entity:
        """Locate the matching ErConfig for a target class via compatibility check."""
        for kls, cfg in self.er_configs_map.items():
            if class_util.is_compatible_type(target, kls):
                return cfg
        raise AttributeError(f'No ErConfig found for {target}')

    def _identify_relationship(self, config: Entity, name: str) -> Relationship:
        """Find the relationship matching name."""
        for rel in config.relationships:
            if rel.name == name:
                return rel
        raise AttributeError(
            f'Relationship with name "{name}" not found in "{config.kls}"'
        )

    def prepare(self, kls: type):
        """Auto-generate resolve_XXX methods for fields annotated with AutoLoad metadata.

        For each pydantic field carrying AutoLoad, create a resolve method that uses the
        corresponding relationship's loader via LoaderDepend.
        """
        auto_loader_fields = list(_get_pydantic_field_items_with_load_by(kls))

        if not auto_loader_fields:
            return

        if self.er_configs_map is None:
            raise ValueError('er_configs_map is None, cannot identify config')

        config = self._identify_entity(kls)

        needs_rebuild = False

        for field_name, annotation, loader_info in auto_loader_fields:
            method_name = f'{const.RESOLVE_PREFIX}{field_name}'
            if hasattr(kls, method_name):
                logger.warning(
                    f'{method_name} already exists in {kls}, skipping auto-generation.'
                )
                continue

            lookup_key = loader_info.origin if loader_info.origin else field_name
            relationship = self._identify_relationship(
                config=config,
                name=lookup_key,
            )

            if relationship.loader is None:
                raise AttributeError(f'Loader not provided in relationship for name "{field_name}" in class "{kls}"')

            # Validate that the annotation type is compatible with relationship.target
            if not class_util.is_compatible_type(annotation, relationship.target):
                raise TypeError(
                    f'Type mismatch in {kls.__name__}.{field_name}: '
                    f'annotated type {annotation} is not compatible with '
                    f'relationship target {relationship.target} (name="{lookup_key}")'
                )

            def _handle_fk_none(rel: Relationship):
                """Common logic for handling None foreign key values."""
                fields_set = getattr(rel, 'model_fields_set', set())
                if 'fk_none_default' in fields_set:
                    return rel.fk_none_default  # may be None intentionally
                if rel.fk_none_default_factory is not None:
                    return rel.fk_none_default_factory()
                return None

            def create_resolve_method(key: str, rel: Relationship):  # closure per field
                def resolve_method(self, loader=Loader(rel.loader)):
                    fk = getattr(self, key)
                    if fk is None:
                        return _handle_fk_none(rel)
                    if rel.fk_fn is not None:
                        fk = rel.fk_fn(fk)
                    return loader.load(fk)
                resolve_method.__name__ = method_name
                resolve_method.__qualname__ = f'{kls.__name__}.{method_name}'
                return resolve_method

            def create_resolve_method_with_load_many(key: str, rel: Relationship):  # closure per field
                def resolve_method(self, loader=Loader(rel.loader)):
                    fk = getattr(self, key)
                    if fk is None:
                        return _handle_fk_none(rel)
                    if rel.load_many_fn is not None:
                        fk = rel.load_many_fn(fk)
                    return loader.load_many(fk)
                resolve_method.__name__ = method_name
                resolve_method.__qualname__ = f'{kls.__name__}.{method_name}'
                return resolve_method

            if relationship.load_many:
                setattr(kls, method_name, create_resolve_method_with_load_many(relationship.fk, relationship))
            else:
                setattr(kls, method_name, create_resolve_method(relationship.fk, relationship))

            needs_rebuild = True

        if needs_rebuild:
            kls.model_rebuild(force=True)


def _get_pydantic_field_items_with_load_by(kls) -> Iterator[tuple[str, type, LoaderInfo]]:
    """
    Find fields which have AutoLoad metadata.

    example:

    class A(Base):
        posts: Annotated[List[PostEntity], AutoLoad()] = []
        extra: str = ''

    return ('posts', AutoLoad())
    """
    items = kls.model_fields.items()

    for name, v in items:
        metadata = v.metadata
        for meta in metadata:
            if isinstance(meta, LoaderInfo):
                yield name, v.annotation, meta
