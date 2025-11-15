from dataclasses import dataclass
from typing import Type, Any, Callable, Optional
from pydantic import BaseModel, model_validator, Field


class Relationship(BaseModel):
    field: str  # fk name

    # use biz to distinguish multiple same target_kls under same field
    biz: Optional[str] = Field(default=None, min_length=1) # Optional or non-empty string
    target_kls: Any
    loader: Callable

class ErConfig(BaseModel):
    kls: Type[BaseModel]
    relationships: list[Relationship]

    @model_validator(mode="after")
    def _validate_relationships(self) -> "ErConfig":
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
            key = (r.field, r.biz, _hashable(r.target_kls))
            if key in seen:
                raise ValueError(
                    f"Duplicate relationship detected for (field={r.field!r}, biz={r.biz!r}, target_kls={r.target_kls!r})"
                )
            seen.add(key)

        return self

class ErDiagram(BaseModel):
    configs: list[ErConfig]

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


@dataclass
class LoaderInfo:
    field: str
    biz: Optional[str] = None


def LoadBy(key: str, biz: Optional[str] = None) -> LoaderInfo:
    return LoaderInfo(field=key, biz=biz)