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
            queryset = target_orm_kls.objects.filter(
                **{f"{target_remote_field_name}__in": list(set(keys))}
            )
            queryset = _maybe_use_database(queryset, using)
            queryset = _apply_filters(queryset, filters)
            rows = await _evaluate_queryset(queryset)

            lookup = {getattr(row, target_remote_field_name): row for row in rows}
            return [
                target_dto_kls.model_validate(lookup[key]) if key in lookup else None
                for key in keys
            ]

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
            queryset = target_orm_kls.objects.filter(
                **{f"{target_relation_field_name}__in": list(set(keys))}
            )
            queryset = _maybe_use_database(queryset, using)
            queryset = _apply_filters(queryset, filters)
            rows = await _evaluate_queryset(queryset)

            grouped = defaultdict(list)
            for row in rows:
                grouped[getattr(row, target_relation_field_name)].append(
                    target_dto_kls.model_validate(row)
                )

            return [grouped.get(key, []) for key in keys]

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
            queryset = target_orm_kls.objects.filter(
                **{f"{target_relation_field_name}__in": list(set(keys))}
            )
            queryset = _maybe_use_database(queryset, using)
            queryset = _apply_filters(queryset, filters)
            rows = await _evaluate_queryset(queryset)

            lookup = {getattr(row, target_relation_field_name): row for row in rows}
            return [
                target_dto_kls.model_validate(lookup[key]) if key in lookup else None
                for key in keys
            ]

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
            source_queryset = source_orm_kls.objects.filter(
                **{f"{source_match_field_name}__in": list(set(keys))}
            )
            source_queryset = _maybe_use_database(source_queryset, using)

            target_queryset = target_orm_kls.objects.all()
            target_queryset = _maybe_use_database(target_queryset, using)
            target_queryset = _apply_filters(target_queryset, filters)

            source_queryset = source_queryset.prefetch_related(
                Prefetch(rel_name, queryset=target_queryset, to_attr=prefetch_attr)
            )
            source_rows = await _evaluate_queryset(source_queryset)

            grouped = {}
            for row in source_rows:
                grouped[getattr(row, source_match_field_name)] = [
                    target_dto_kls.model_validate(item)
                    for item in getattr(row, prefetch_attr, [])
                ]

            return [grouped.get(key, []) for key in keys]

    return _finalize_loader_class(_Loader, identity)
