from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Callable

from aiodataloader import DataLoader


def _normalize_identifier(value: str) -> str:
    """Convert arbitrary names to valid class-name fragments."""
    normalized = re.sub(r"[^0-9a-zA-Z_]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "anonymous"


def _build_loader_identity(source_orm_kls: type, rel_name: str, suffix: str) -> str:
    source_name = _normalize_identifier(getattr(source_orm_kls, "__name__", "source"))
    rel_part = _normalize_identifier(rel_name)
    return f"{source_name}_{rel_part}_{suffix}"


def _finalize_loader_class(cls: type[DataLoader], identity: str) -> type[DataLoader]:
    class_name = f"SA_{identity}"
    cls.__name__ = class_name
    cls.__qualname__ = class_name
    cls.__module__ = __name__
    return cls


def _row_get(row: Any, key: str) -> Any:
    mapping = getattr(row, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]
    return getattr(row, key)


def _apply_filters(stmt: Any, filters: list[Any] | None) -> Any:
    if filters:
        return stmt.where(*filters)
    return stmt


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
    # Always include all DTO fields to ensure model_validate can access every attribute.
    # _query_meta may only contain a subset of fields from GraphQL field selection,
    # which would cause load_only to defer non-selected columns and break model_validate.
    dto_fields = _get_default_fields(target_dto_kls)
    effective_fields = _dedupe_fields([*dto_fields, *(extra_fields or [])])
    loader._effective_query_fields = effective_fields
    return effective_fields


def _apply_load_only(
    stmt: Any,
    target_orm_kls: type,
    fields: list[str],
) -> Any:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy.orm import load_only

    mapper = sa_inspect(target_orm_kls)
    rel_keys = {rel.key for rel in mapper.relationships}
    attrs = [
        getattr(target_orm_kls, field)
        for field in fields
        if hasattr(target_orm_kls, field) and field not in rel_keys
    ]
    if attrs:
        return stmt.options(load_only(*attrs))
    return stmt


def create_many_to_one_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    target_remote_col_name: str,
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import select

            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[self.target_remote_col_name],
            )

            async with self.session_factory() as session:
                stmt = select(self.target_orm_kls)
                stmt = _apply_load_only(stmt, self.target_orm_kls, effective_fields)
                stmt = stmt.where(
                    getattr(self.target_orm_kls, self.target_remote_col_name).in_(keys)
                )
                stmt = _apply_filters(stmt, self.filters)
                rows = (await session.scalars(stmt)).all()

            lookup = {getattr(row, self.target_remote_col_name): row for row in rows}
            return [
                self.target_dto_kls.model_validate(lookup[k]) if k in lookup else None
                for k in keys
            ]

    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.target_remote_col_name = target_remote_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "M2O"),
    )


def create_one_to_many_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    target_fk_col_name: str,
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import select

            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[self.target_fk_col_name],
            )

            async with self.session_factory() as session:
                stmt = select(self.target_orm_kls)
                stmt = _apply_load_only(stmt, self.target_orm_kls, effective_fields)
                stmt = stmt.where(
                    getattr(self.target_orm_kls, self.target_fk_col_name).in_(keys)
                )
                stmt = _apply_filters(stmt, self.filters)
                rows = (await session.scalars(stmt)).all()

            grouped = defaultdict(list)
            for row in rows:
                grouped[getattr(row, self.target_fk_col_name)].append(
                    self.target_dto_kls.model_validate(row)
                )

            return [grouped.get(k, []) for k in keys]

    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.target_fk_col_name = target_fk_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "O2M"),
    )


def create_reverse_one_to_one_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    target_fk_col_name: str,
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import select

            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[self.target_fk_col_name],
            )

            async with self.session_factory() as session:
                stmt = select(self.target_orm_kls)
                stmt = _apply_load_only(stmt, self.target_orm_kls, effective_fields)
                stmt = stmt.where(
                    getattr(self.target_orm_kls, self.target_fk_col_name).in_(keys)
                )
                stmt = _apply_filters(stmt, self.filters)
                rows = (await session.scalars(stmt)).all()

            lookup = {getattr(row, self.target_fk_col_name): row for row in rows}
            return [
                self.target_dto_kls.model_validate(lookup[k]) if k in lookup else None
                for k in keys
            ]

    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.target_fk_col_name = target_fk_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "RO2O"),
    )


def create_many_to_many_loader(
    *,
    source_orm_kls: type,
    rel_name: str,
    target_orm_kls: type,
    target_dto_kls: type,
    secondary_table: Any,
    secondary_local_col_name: str,
    secondary_remote_col_name: str,
    target_match_col_name: str,
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import select

            effective_fields = _get_effective_query_fields(
                self,
                self.target_dto_kls,
                extra_fields=[self.target_match_col_name],
            )

            async with self.session_factory() as session:
                join_stmt = select(self.secondary_table).where(
                    getattr(self.secondary_table.c, self.secondary_local_col_name).in_(keys)
                )
                join_rows = (await session.execute(join_stmt)).all()

                target_keys = list(
                    {_row_get(row, self.secondary_remote_col_name) for row in join_rows}
                )
                if not target_keys:
                    self._effective_query_fields = effective_fields
                    return [[] for _ in keys]

                target_stmt = select(self.target_orm_kls)
                target_stmt = _apply_load_only(target_stmt, self.target_orm_kls, effective_fields)
                target_stmt = target_stmt.where(
                    getattr(self.target_orm_kls, self.target_match_col_name).in_(target_keys)
                )
                target_stmt = _apply_filters(target_stmt, self.filters)
                target_rows = (await session.scalars(target_stmt)).all()

            target_map = {
                getattr(row, self.target_match_col_name): self.target_dto_kls.model_validate(row)
                for row in target_rows
            }

            grouped = defaultdict(list)
            for join_row in join_rows:
                target_obj = target_map.get(_row_get(join_row, self.secondary_remote_col_name))
                if target_obj is not None:
                    grouped[_row_get(join_row, self.secondary_local_col_name)].append(target_obj)

            return [grouped.get(k, []) for k in keys]

    _Loader.target_orm_kls = target_orm_kls
    _Loader.target_dto_kls = target_dto_kls
    _Loader.secondary_table = secondary_table
    _Loader.secondary_local_col_name = secondary_local_col_name
    _Loader.secondary_remote_col_name = secondary_remote_col_name
    _Loader.target_match_col_name = target_match_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "M2M"),
    )
