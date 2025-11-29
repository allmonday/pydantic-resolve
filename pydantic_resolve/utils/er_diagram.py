from dataclasses import dataclass
from typing import Type, Any, Callable, Optional
from pydantic import BaseModel, model_validator, Field
import warnings

import pydantic_resolve.constant as const
from pydantic_resolve.utils import class_util
from pydantic_resolve.utils.depend import LoaderDepend


class BaseLinkProps(BaseModel):
    field_none_default: Optional[Any] = None
    field_none_default_factory: Optional[Callable[[], Any]] = None

    # load_many
    load_many: bool = False

    # in case of fk itself is not list, for example: str
    # and need to seperate manually,
    # call load_many_fn to handle it.
    load_many_fn: Optional[Callable[[Any], Any]] = None  

    loader: Optional[Callable] = None

class Link(BaseLinkProps):
    biz: str

    # specific a loader which only return one field of target model
    field_name: Optional[str] = None  
    
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
    kls: Type[BaseModel]
    relationships: list[Relationship | MultipleRelationship]

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

        return self

class ErDiagram(BaseModel):
    configs: list[Entity]

    @model_validator(mode="after")
    def _validate_configs(self) -> "ErDiagram":
        cfgs = self.configs or []
        seen = set()
        for cfg in cfgs:
            kls = cfg.kls
            if kls in seen:
                raise ValueError(f"Duplicate config.kls detected: {kls}")
            seen.add(kls)
        return self

    description: Optional[str] = None


@dataclass
class LoaderInfo:
    field: str
    biz: Optional[str] = None


def LoadBy(key: str, biz: Optional[str] = None) -> LoaderInfo:
    return LoaderInfo(field=key, biz=biz)


class ErLoaderPreGenerator:
    def __init__(self, er_diagram: Optional[ErDiagram]) -> None:
        self.er_configs_map = {config.kls: config for config in er_diagram.configs} if er_diagram else None

    def _identify_entity(self, target: Type) -> Entity:
        """Locate the matching ErConfig for a target class via compatibility check."""
        for kls, cfg in self.er_configs_map.items():
            if class_util.is_compatible_type(target, kls):
                return cfg
        raise AttributeError(f'No ErConfig found for {target.__name__}')

    def _identify_relationship(self, config: Entity, loadby: str, biz: Optional[str], target_kls: Type) -> Relationship:
        """
            Find the relationship matching (field=loadby, biz, target_kls).

            if biz is provided and field_name of Link is set, validate the target_kls with target_kls's field_name type
        """
        for rel in config.relationships:
            if rel.field != loadby:
                continue

            if isinstance(rel, Relationship) and class_util.is_compatible_type(target_kls, rel.target_kls):
                return rel
            
            elif isinstance(rel, MultipleRelationship):
                for link in rel.links:
                    if link.biz == biz:
                        if link.field_name:
                            # TODO: validate types, currently just bypass
                            # str == kls[field_name]
                            # list[str] == list[kls[field_name]]
                            # currently field name can provide field hint for voyager
                            return link

                        elif class_util.is_compatible_type(target_kls, rel.target_kls):
                            return link

        raise AttributeError(
            f'Relationship for "{target_kls.__name__}" using "{loadby}", biz: "{biz}", not found'
        )

    def prepare(self, kls: Type):
        """Auto-generate resolve_XXX methods for fields annotated with LoadBy metadata.

        For each pydantic field carrying LoadBy, create a resolve method that uses the
        corresponding relationship's loader via LoaderDepend.
        """
        auto_loader_fields = list(class_util.get_pydantic_field_items_with_load_by(kls))

        if not auto_loader_fields:
            return 

        if self.er_configs_map is None:
            raise ValueError('er_configs_map is None, cannot identify config')

        config = self._identify_entity(kls)

        for field_name, loader_info, annotation in auto_loader_fields:
            method_name = f'{const.RESOLVE_PREFIX}{field_name}'
            if hasattr(kls, method_name):
                warnings.warn(
                    f'{method_name} already exists in {kls.__name__}, skipping auto-generation.'
                )
                continue

            relationship = self._identify_relationship(
                config=config,
                loadby=loader_info.field,
                biz=loader_info.biz,
                target_kls=annotation,
            )

            if relationship.loader is None:
                # loader is optional in Relationship, but required for auto-generation
                raise AttributeError(f'Loader not provided in relationship for field "{loader_info.field}" in class "{kls.__name__}"')

            def create_resolve_method(key: str, rel: Relationship):  # closure per field
                def resolve_method(self, loader=LoaderDepend(rel.loader)):
                    fk = getattr(self, key)
                    if fk is None:
                        fields_set = getattr(rel, 'model_fields_set', set())
                        if 'field_none_default' in fields_set:
                            return rel.field_none_default  # may be None intentionally

                        if rel.field_none_default_factory is not None:
                            return rel.field_none_default_factory()
                        return None
                    return loader.load(fk)
                resolve_method.__name__ = method_name
                resolve_method.__qualname__ = f'{kls.__name__}.{method_name}'
                return resolve_method

            def create_resolve_method_with_load_many(key: str, rel: Relationship):  # closure per field
                def resolve_method(self, loader=LoaderDepend(rel.loader)):
                    fk = getattr(self, key)
                    if fk is None:
                        fields_set = getattr(rel, 'model_fields_set', set())
                        if 'field_none_default' in fields_set:
                            return rel.field_none_default  # may be None intentionally

                        if rel.field_none_default_factory is not None:
                            return rel.field_none_default_factory()
                        return None

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
