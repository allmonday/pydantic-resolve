from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from aiodataloader import DataLoader
from asgiref.sync import sync_to_async


def _normalize_identifier(value: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z_]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "anonymous"


def _build_loader_identity(source_orm_kls: type, rel_name: str, suffix: str) -> str:
    source_name = _normalize_identifier(getattr(source_orm_kls, "__name__", "source"))
    rel_part = _normalize_identifier(rel_name)
    return f"{source_name}_{rel_part}_{suffix}"


def _finalize_loader_class(cls: type[DataLoader], identity: str) -> type[DataLoader]:
    class_name = f"DJ_{identity}"
    cls.__name__ = class_name
    cls.__qualname__ = class_name
    cls.__module__ = __name__
    return cls


def _resolve_using(using: Any) -> Any:
    if callable(using):
        return using()
    return using


def _maybe_use_database(queryset: Any, using: Any) -> Any:
    alias = _resolve_using(using)
    if alias is not None:
        return queryset.using(alias)
    return queryset


def _apply_filters(queryset: Any, filters: list[Any] | None) -> Any:
    if filters:
        return queryset.filter(*filters)
    return queryset


def _dedupe_fields(fields: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for field in fields:
        if field not in seen:
            deduped.append(field)
            seen.add(field)
    return deduped


def _get_default_fields(target_dto_kls: type) -> list[str]:
    return list(target_dto_kls.model_fields.keys())


def _get_effective_query_fields(
    loader: DataLoader,
    target_dto_kls: type,
    extra_fields: list[str] | None = None,
) -> list[str]:
    query_meta = getattr(loader, "_query_meta", None)
    requested_fields = query_meta["fields"] if query_meta else _get_default_fields(target_dto_kls)
    effective_fields = _dedupe_fields([*requested_fields, *(extra_fields or [])])
    loader._effective_query_fields = effective_fields
    return effective_fields


def _apply_only(queryset: Any, fields: list[str]) -> Any:
    if fields:
        return queryset.only(*fields)
    return queryset


async def _evaluate_queryset(queryset: Any) -> list[Any]:
    return await sync_to_async(list, thread_sensitive=True)(queryset)


def create_many_to_one_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    target_remote_field_name: str,
    using: Any = None,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    identity = _build_loader_identity(source_orm_kls, rel_name, "M2O")

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[self.target_remote_field_name],
            )

            queryset = self.target_orm_kls.objects.filter(
                **{f"{self.target_remote_field_name}__in": list(set(keys))}
            )
            queryset = _maybe_use_database(queryset, self.using)
            queryset = _apply_filters(queryset, self.filters)
            queryset = _apply_only(queryset, effective_fields)
            rows = await _evaluate_queryset(queryset)

            lookup = {getattr(row, self.target_remote_field_name): row for row in rows}
            return [
                self.target_dto_kls.model_validate(lookup[key]) if key in lookup else None
                for key in keys
            ]

    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.target_remote_field_name = target_remote_field_name
    _Loader.using = staticmethod(using) if callable(using) else using
    _Loader.filters = filters

    return _finalize_loader_class(_Loader, identity)


def create_one_to_many_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    target_relation_field_name: str,
    using: Any = None,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    identity = _build_loader_identity(source_orm_kls, rel_name, "O2M")

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[self.target_relation_field_name],
            )

            queryset = self.target_orm_kls.objects.filter(
                **{f"{self.target_relation_field_name}__in": list(set(keys))}
            )
            queryset = _maybe_use_database(queryset, self.using)
            queryset = _apply_filters(queryset, self.filters)
            queryset = _apply_only(queryset, effective_fields)
            rows = await _evaluate_queryset(queryset)

            grouped = defaultdict(list)
            for row in rows:
                grouped[getattr(row, self.target_relation_field_name)].append(
                    self.target_dto_kls.model_validate(row)
                )

            return [grouped.get(key, []) for key in keys]

    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.target_relation_field_name = target_relation_field_name
    _Loader.using = staticmethod(using) if callable(using) else using
    _Loader.filters = filters

    return _finalize_loader_class(_Loader, identity)


def create_reverse_one_to_one_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    target_relation_field_name: str,
    using: Any = None,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    identity = _build_loader_identity(source_orm_kls, rel_name, "RO2O")

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[self.target_relation_field_name],
            )

            queryset = self.target_orm_kls.objects.filter(
                **{f"{self.target_relation_field_name}__in": list(set(keys))}
            )
            queryset = _maybe_use_database(queryset, self.using)
            queryset = _apply_filters(queryset, self.filters)
            queryset = _apply_only(queryset, effective_fields)
            rows = await _evaluate_queryset(queryset)

            lookup = {getattr(row, self.target_relation_field_name): row for row in rows}
            return [
                self.target_dto_kls.model_validate(lookup[key]) if key in lookup else None
                for key in keys
            ]

    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.target_relation_field_name = target_relation_field_name
    _Loader.using = staticmethod(using) if callable(using) else using
    _Loader.filters = filters

    return _finalize_loader_class(_Loader, identity)


def create_many_to_many_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    source_match_field_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    using: Any = None,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    from django.db.models import Prefetch

    identity = _build_loader_identity(source_orm_kls, rel_name, "M2M")
    prefetch_attr = f"pydantic_resolve_{identity}"

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            target_pk_field = self.target_orm_kls._meta.pk.attname
            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[target_pk_field],
            )

            source_queryset = self.source_orm_kls.objects.filter(
                **{f"{self.source_match_field_name}__in": list(set(keys))}
            )
            source_queryset = _maybe_use_database(source_queryset, self.using)

            target_queryset = self.target_orm_kls.objects.all()
            target_queryset = _maybe_use_database(target_queryset, self.using)
            target_queryset = _apply_filters(target_queryset, self.filters)
            target_queryset = _apply_only(target_queryset, effective_fields)

            source_queryset = source_queryset.prefetch_related(
                Prefetch(rel_name, queryset=target_queryset, to_attr=self.prefetch_attr)
            )
            source_rows = await _evaluate_queryset(source_queryset)

            grouped = {}
            for row in source_rows:
                grouped[getattr(row, self.source_match_field_name)] = [
                    self.target_dto_kls.model_validate(item)
                    for item in getattr(row, self.prefetch_attr, [])
                ]

            return [grouped.get(key, []) for key in keys]

    _Loader.source_orm_kls = source_orm_kls
    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.source_match_field_name = source_match_field_name
    _Loader.using = staticmethod(using) if callable(using) else using
    _Loader.filters = filters
    _Loader.prefetch_attr = prefetch_attr

    return _finalize_loader_class(_Loader, identity)
