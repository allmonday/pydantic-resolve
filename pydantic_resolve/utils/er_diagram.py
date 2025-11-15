from dataclasses import dataclass
from typing import Type, TypeVar, Any, Callable, Optional
from pydantic import BaseModel, model_validator
from aiodataloader import DataLoader


class Relationship(BaseModel):
    field: str  # fk name
    biz: Optional[str] = None  # use biz to distinguish multiple target_kls under same field
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

        # 1) Disallow duplicate (field, biz, target_kls) triples
        seen = set()
        for r in rels:
            key = (r.field, r.biz, _hashable(r.target_kls))
            if key in seen:
                raise ValueError(
                    f"Duplicate relationship detected for (field={r.field!r}, biz={r.biz!r}, target_kls={r.target_kls!r})"
                )
            seen.add(key)

        # 2) For each field: if multiple distinct target_kls exist, require non-empty and unique biz per field
        by_field: dict[str, list[Relationship]] = {}
        for r in rels:
            by_field.setdefault(r.field, []).append(r)

        for field, items in by_field.items():
            unique_targets = {_hashable(it.target_kls) for it in items}
            if len(unique_targets) > 1:
                # require biz to be provided and unique within this field to differentiate
                biz_values = [it.biz for it in items]
                if any(b is None or (isinstance(b, str) and b.strip() == "") for b in biz_values):
                    raise ValueError(
                        f"Field {field!r} maps to multiple target_kls; a non-empty 'biz' must be provided to distinguish them."
                    )
                if len(set(biz_values)) != len(biz_values):
                    raise ValueError(
                        f"Field {field!r} has multiple target_kls; 'biz' values must be unique under the same field."
                    )

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
    by: str


def LoadBy(key: str) -> LoaderInfo:
    return LoaderInfo(by=key)