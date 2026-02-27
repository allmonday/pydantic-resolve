from dataclasses import dataclass
from typing import Iterator, Any, Callable, Optional
from pydantic import BaseModel, model_validator, Field
import warnings
import importlib
import functools

import pydantic_resolve.constant as const
from pydantic_resolve.utils import class_util, types
from pydantic_resolve.utils.depend import LoaderDepend


class QueryConfig(BaseModel):
    """Query 方法配置，用于在 Entity 外部定义 Query 方法并动态绑定。"""
    method: Callable
    name: Optional[str] = None
    description: Optional[str] = None


class MutationConfig(BaseModel):
    """Mutation 方法配置，用于在 Entity 外部定义 Mutation 方法并动态绑定。"""
    method: Callable
    name: Optional[str] = None
    description: Optional[str] = None


class BaseLinkProps(BaseModel):
    # field_fn will not work if load_many is True, use load_many_fn instead
    field_fn: Callable | None = None

    field_none_default: Any | None = None
    field_none_default_factory: Callable[[], Any] | None = None

    # load_many
    load_many: bool = False

    # in case of fk itself is not list, for example: str
    # and need to separate manually,
    # call load_many_fn to handle it.
    load_many_fn: Callable[[Any], Any] | None = None

    loader: Callable | None = None

    # GraphQL 查询字段名（用于暴露嵌套查询）
    default_field_name: str | None = None

class Link(BaseLinkProps):
    biz: str

    # specific a loader which only return one field of target model
    field_name: str | None = None  
    
class MultipleRelationship(BaseModel):
    field: str  # fk name
    # use biz to distinguish multiple same target_kls under same field
    target_kls: Any
    links: list[Link] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_links(self) -> "MultipleRelationship":
        biz_set = set()
        for link in self.links:
            if link.biz in biz_set:
                raise ValueError(
                    f"Duplicate link.biz detected in MultipleRelationship for field {self.field!r}: {link.biz!r}"
                )
            biz_set.add(link.biz)
        return self


class Relationship(BaseLinkProps):
    field: str  # fk name
    target_kls: Any

    @model_validator(mode="after")
    def _validate_defaults(self) -> "Relationship":
        # Avoid evaluating the deprecated fallback unless necessary to prevent warnings.
        fields_set = getattr(self, 'model_fields_set', set())
        val_set = 'field_none_default' in fields_set
        factory_set = 'field_none_default_factory' in fields_set
        if val_set and factory_set:
            raise ValueError(
                "field_none_default and field_none_default_factory cannot both be defined"
            )
        return self

class Entity(BaseModel):
    kls: type[BaseModel]
    relationships: list[Relationship | MultipleRelationship] = Field(default_factory=list)
    queries: list[QueryConfig] = Field(default_factory=list)
    mutations: list[MutationConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_relationships(self) -> "Entity":
        rels = self.relationships or []

        # helper to make potentially unhashable target_kls hashable for set/dict keys
        def _hashable(x: Any) -> Any:
            try:
                hash(x)
                return x
            except TypeError:
                return repr(x)

        # Disallow duplicate (field, biz, target_kls) triples
        seen = set()
        for r in rels:
            key = (r.field, _hashable(r.target_kls))
            if key in seen:
                raise ValueError(
                    f"Duplicate relationship detected for (field={r.field!r}, target_kls={r.target_kls!r})"
                )
            seen.add(key)

        # 验证 default_field_name 冲突
        self._validate_field_name_conflicts()

        return self

    def _validate_field_name_conflicts(self) -> None:
        """检测 default_field_name 的命名冲突。"""
        from typing import get_type_hints

        # 1. 收集标量字段
        try:
            scalar_fields = set(get_type_hints(self.kls).keys())
        except Exception:
            scalar_fields = set()

        # 2. 收集关系字段的 default_field_name
        # 使用元组 (source_type, source_info) 来跟踪来源
        # source_type: 'Relationship' 或 'Link'
        # source_info: 关系的详细信息
        relationship_fields = {}

        def _get_rel_source_info(rel, link=None):
            """获取关系来源的描述信息"""
            if isinstance(rel, Relationship):
                return ('Relationship', f"Relationship(field={rel.field})")
            elif isinstance(rel, MultipleRelationship) and link:
                return ('Link', f"Link(biz={link.biz}) in MultipleRelationship(field={rel.field})")
            return ('Unknown', 'Unknown')

        for rel in self.relationships or []:
            if isinstance(rel, Relationship) and rel.default_field_name:
                field_name = rel.default_field_name
                source_type, source_info = _get_rel_source_info(rel)

                # 检查重复的关系字段
                if field_name in relationship_fields:
                    prev_source_type, prev_source_info = relationship_fields[field_name]
                    raise ValueError(
                        f"Field name conflict in {self.kls.__name__}: '{field_name}' - "
                        f"multiple relationships use the same default_field_name. "
                        f"Conflict between {prev_source_info} and {source_info}"
                    )

                relationship_fields[field_name] = (source_type, source_info)

                # 检查与标量字段的冲突
                if field_name in scalar_fields:
                    raise ValueError(
                        f"Field name conflict in {self.kls.__name__}: '{field_name}' - "
                        f"default_field_name conflicts with scalar field. "
                        f"{source_info}, target_kls={rel.target_kls}"
                    )

            elif isinstance(rel, MultipleRelationship):
                # 检查 MultipleRelationship 的 links
                for link in rel.links:
                    if link.default_field_name:
                        field_name = link.default_field_name
                        source_type, source_info = _get_rel_source_info(rel, link)

                        # 检查重复的关系字段
                        if field_name in relationship_fields:
                            prev_source_type, prev_source_info = relationship_fields[field_name]
                            raise ValueError(
                                f"Field name conflict in {self.kls.__name__}: '{field_name}' - "
                                f"multiple relationships use the same default_field_name. "
                                f"Conflict between {prev_source_info} and {source_info}"
                            )

                        relationship_fields[field_name] = (source_type, source_info)

                        # 检查与标量字段的冲突
                        if field_name in scalar_fields:
                            raise ValueError(
                                f"Field name conflict in {self.kls.__name__}: '{field_name}' - "
                                f"default_field_name conflicts with scalar field. "
                                f"{source_info}, target_kls={rel.target_kls}"
                            )

        # 3. 检查与父类字段的冲突
        for base_cls in self.kls.__mro__[1:]:  # 跳过自身
            if base_cls is object:
                continue
            try:
                base_fields = set(get_type_hints(base_cls).keys())
            except Exception:
                continue

            for field_name, (source_type, source_info) in relationship_fields.items():
                if field_name in base_fields:
                    raise ValueError(
                        f"Field name conflict in {self.kls.__name__}: '{field_name}' - "
                        f"relationship field conflicts with inherited field from {base_cls.__name__}. "
                        f"{source_info}"
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

        # 动态绑定 queries 和 mutations
        self._bind_query_mutation_methods()
        return self

    description: str | None = None

    def _bind_query_mutation_methods(self) -> None:
        """将 queries/mutations 配置中的方法动态绑定到 Entity 类。

        使用包装器自动忽略 cls 参数，让用户方法看起来像普通函数。
        """
        for entity_cfg in self.configs:
            kls = entity_cfg.kls

            for query_cfg in entity_cfg.queries:
                method = query_cfg.method
                method_name = method.__name__

                # 创建包装器，自动忽略 cls 参数
                @functools.wraps(method)
                def query_wrapper(cls, *args, _method=method, **kwargs):
                    return _method(*args, **kwargs)

                # 设置元数据（与 @query 装饰器一致）
                query_wrapper._pydantic_resolve_query = True
                query_wrapper._pydantic_resolve_query_name = query_cfg.name
                query_wrapper._pydantic_resolve_query_description = query_cfg.description

                # 绑定为 classmethod
                setattr(kls, method_name, classmethod(query_wrapper))

            for mutation_cfg in entity_cfg.mutations:
                method = mutation_cfg.method
                method_name = method.__name__

                # 创建包装器，自动忽略 cls 参数
                @functools.wraps(method)
                def mutation_wrapper(cls, *args, _method=method, **kwargs):
                    return _method(*args, **kwargs)

                # 设置元数据（与 @mutation 装饰器一致）
                mutation_wrapper._pydantic_resolve_mutation = True
                mutation_wrapper._pydantic_resolve_mutation_name = mutation_cfg.name
                mutation_wrapper._pydantic_resolve_mutation_description = mutation_cfg.description

                # 绑定为 classmethod
                setattr(kls, method_name, classmethod(mutation_wrapper))


class BaseEntity:  # just type (TODO: optimize)
    entities: list[Entity]
    def get_diagram() -> ErDiagram:
        raise NotImplementedError


@dataclass
class LoaderInfo:
    field: str
    biz: str | None = None
    origin_kls: type | None = None


def LoadBy(key: str, biz: str | None = None, origin_kls: type | None = None) -> LoaderInfo:
    return LoaderInfo(field=key, biz=biz, origin_kls=origin_kls)


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
                        'target_kls': _resolve_ref(rel.target_kls, module_name),
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
            # Check for inline relationships, __relationships__ or __pydantic_resolve_relationships__
            # __pydantic_resolve_relationships__ has higher priority
            inline_rels = getattr(cls, const.ER_DIAGRAM_INLINE_RELATIONSHIPS, None)
            if inline_rels is None:
                inline_rels = getattr(cls, const.ER_DIAGRAM_INLINE_RELATIONSHIPS_SHORT, None)
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

    def _identify_relationship(self, config: Entity, loader_info: LoaderInfo, target_kls: type) -> Relationship:
        """
            Find the relationship matching (field=loadby, biz, target_kls).

            if biz is provided and field_name of Link is set, validate the target_kls with target_kls's field_name type
        """
        for rel in config.relationships:
            if rel.field != loader_info.field:
                continue

            if isinstance(rel, Relationship) and class_util.is_compatible_type(target_kls, rel.target_kls):
                return rel
            
            elif isinstance(rel, MultipleRelationship):
                for link in rel.links:
                    if link.biz == loader_info.biz:
                        if link.field_name:
                            if loader_info.origin_kls is None:
                                raise ValueError( 'origin_kls must be provided in LoaderInfo when field_name is set in Link')
                            else:
                                if class_util.is_compatible_type(loader_info.origin_kls, rel.target_kls):
                                    # TODO: validate types, currently just bypass
                                    # str == kls[field_name]
                                    # list[str] == list[kls[field_name]]
                                    # currently field name can provide field hint for voyager
                                    # and leave validation to pydantic
                                    return link
                                else:
                                    raise TypeError( f'Target_kls {target_kls} is not compatible with origin_kls {loader_info.origin_kls} in Link for biz {link.biz}')
                        elif class_util.is_compatible_type(target_kls, rel.target_kls):
                            return link

        raise AttributeError(
            f'Relationship from "{config.kls}" to "{target_kls}" using "{loader_info.field}", biz: "{loader_info.biz}", not found'
        )

    def prepare(self, kls: type):
        """Auto-generate resolve_XXX methods for fields annotated with LoadBy metadata.

        For each pydantic field carrying LoadBy, create a resolve method that uses the
        corresponding relationship's loader via LoaderDepend.
        """
        auto_loader_fields = list(_get_pydantic_field_items_with_load_by(kls))

        if not auto_loader_fields:
            return 

        if self.er_configs_map is None:
            raise ValueError('er_configs_map is None, cannot identify config')

        config = self._identify_entity(kls)

        for field_name, loader_info, annotation in auto_loader_fields:
            method_name = f'{const.RESOLVE_PREFIX}{field_name}'
            if hasattr(kls, method_name):
                warnings.warn(
                    f'{method_name} already exists in {kls}, skipping auto-generation.'
                )
                continue

            relationship = self._identify_relationship(
                config=config,
                loader_info=loader_info,
                target_kls=annotation,
            )

            if relationship.loader is None:
                # loader is optional in Relationship, but required for auto-generation
                raise AttributeError(f'Loader not provided in relationship for field "{loader_info.field}" in class "{kls}"')

            def _handle_fk_none(rel: Relationship):
                """Common logic for handling None foreign key values."""
                fields_set = getattr(rel, 'model_fields_set', set())
                if 'field_none_default' in fields_set:
                    return rel.field_none_default  # may be None intentionally
                if rel.field_none_default_factory is not None:
                    return rel.field_none_default_factory()
                return None

            def create_resolve_method(key: str, rel: Relationship):  # closure per field
                def resolve_method(self, loader=LoaderDepend(rel.loader)):
                    fk = getattr(self, key)
                    if fk is None:
                        return _handle_fk_none(rel)
                    if rel.field_fn is not None:
                        fk = rel.field_fn(fk)
                    return loader.load(fk)
                resolve_method.__name__ = method_name
                resolve_method.__qualname__ = f'{kls.__name__}.{method_name}'
                return resolve_method

            def create_resolve_method_with_load_many(key: str, rel: Relationship):  # closure per field
                def resolve_method(self, loader=LoaderDepend(rel.loader)):
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
                setattr(kls, method_name, create_resolve_method_with_load_many(loader_info.field, relationship))
            else:
                setattr(kls, method_name, create_resolve_method(loader_info.field, relationship))


def _get_pydantic_field_items_with_load_by(kls) -> Iterator[tuple[str, LoaderInfo, type]]:
    """
    find fields which have LoadBy metadata.

    example:

    class Base(BaseModel):
        id: int
        name: str
        b_id: int

    class B(BaseModel):
        id: int
        name: str

    class A(Base):
        b: Annotated[Optional[B], LoadBy('b_id')] = None
        extra: str = ''

    return ('b', LoadBy('b_id'))
    """
    items = kls.model_fields.items()

    for name, v in items:
        metadata = v.metadata
        for meta in metadata:
            if isinstance(meta, LoaderInfo):
                yield name, meta, v.annotation

