from typing import Optional
import pydantic_resolve.constant as const
from pydantic_resolve.utils.er_diagram import ErConfig, Relationship
from pydantic_resolve.exceptions import (
    DuplicateErConfigError,
    DuplicateRelationshipError,
    InvalidRelationshipError,
)
import pydantic_resolve.resolver as resolver

def ensure_unique_er_configs(er_configs: Optional[list[ErConfig]]) -> None:
    """Ensure each ErConfig targets a unique class and relationships are valid.

    Validations:
    - ErConfig.kls must be unique across all items
    - Each ErConfig.relationships must not contain duplicate 'field' entries
    - Relationship.field/target_kls/loader must be provided (non-empty)
    """
    if not er_configs:
        return

    seen: set[type] = set()
    duplicates: set[type] = set()

    for cfg in er_configs:
        kls = cfg.kls
        if kls in seen:
            duplicates.add(kls)
        else:
            seen.add(kls)

    if duplicates:
        names = ', '.join(sorted(cls.__name__ for cls in duplicates))
        raise DuplicateErConfigError(f'duplicate ErConfig.kls detected: {names}')

    # Validate relationships within each ErConfig
    for cfg in er_configs:
        field_seen: set[str] = set()
        field_dups: set[str] = set()

        for rel in cfg.relationships or []:
            # validate required fields
            if not isinstance(rel, Relationship):
                raise InvalidRelationshipError(f'invalid relationship item on {cfg.kls.__name__}: {rel!r}')

            if not rel.field or not isinstance(rel.field, str):
                raise InvalidRelationshipError(f'relationship.field must be non-empty str on {cfg.kls.__name__}')

            if rel.target_kls is None:
                raise InvalidRelationshipError(f'relationship.target_kls must not be None on {cfg.kls.__name__}')

            # if it's a list, it must not be empty and must not contain None
            if isinstance(rel.target_kls, list):
                if len(rel.target_kls) == 0:
                    raise InvalidRelationshipError(f'relationship.target_kls list must not be empty on {cfg.kls.__name__}')
                if any(t is None for t in rel.target_kls):
                    raise InvalidRelationshipError(f'relationship.target_kls must not contain None on {cfg.kls.__name__}')

            if rel.loader is None:
                raise InvalidRelationshipError(f'relationship.loader must not be None on {cfg.kls.__name__}')

            # check duplicate field within the same ErConfig
            if rel.field in field_seen:
                field_dups.add(rel.field)
            else:
                field_seen.add(rel.field)

        if field_dups:
            dups = ', '.join(sorted(field_dups))
            raise DuplicateRelationshipError(f'duplicate relationships by field on {cfg.kls.__name__}: {dups}')


def config_resolver(name: Optional[str]=None, 
                    er_configs: Optional[list[ErConfig]]=None):
    ensure_unique_er_configs(er_configs)
    new_resolver = type(
        name or resolver.Resolver.__name__,
        resolver.Resolver.__bases__,
        dict(resolver.Resolver.__dict__)
    )
    setattr(new_resolver, const.ER_DIAGRAM, er_configs)
    return new_resolver


def config_global_resolver(er_configs: Optional[list[ErConfig]]=None):
    ensure_unique_er_configs(er_configs)
    setattr(resolver.Resolver, const.ER_DIAGRAM, er_configs)