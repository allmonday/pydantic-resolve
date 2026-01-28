from dataclasses import dataclass
from typing import Iterator
import pydantic_resolve.constant as const

@dataclass
class ExposeInfo:
    alias: str

def ExposeAs(alias: str) -> ExposeInfo:
    return ExposeInfo(alias=alias)


def pre_generate_expose_config(kls):
    """
    iterate kls fields, check and collect field who's annotated metadata for ExposeAs exists
    if kls's const.EXPOSE_CONFIGURATION exists and the fields is not empty, raise exception

    generate the configuration such as 
    { field_name: alias }
    and set it into kls's const.EXPOSE_CONFIGURATION
    """
    fields = list(_get_pydantic_field_items_with_expose_as(kls))
    if not fields:
        return

    if hasattr(kls, const.EXPOSE_TO_DESCENDANT):
        raise AttributeError(
            f"{const.EXPOSE_TO_DESCENDANT} already exists; cannot use ExposeAs annotations at the same time"
        )

    expose_dict = {name: meta.alias for name, meta in fields}
    setattr(kls, const.EXPOSE_TO_DESCENDANT, expose_dict)

def _get_pydantic_field_items_with_expose_as(kls) -> Iterator[tuple[str, ExposeInfo, type]]:
    items = kls.model_fields.items()

    for name, v in items:
        metadata = v.metadata
        for meta in metadata:
            if isinstance(meta, ExposeInfo):
                yield name, meta