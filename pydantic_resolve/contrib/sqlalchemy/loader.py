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

            async with session_factory() as session:
                stmt = select(target_orm_kls).where(
                    getattr(target_orm_kls, target_remote_col_name).in_(keys)
                )
                stmt = _apply_filters(stmt, filters)
                rows = (await session.scalars(stmt)).all()

            lookup = {getattr(row, target_remote_col_name): row for row in rows}
            return [
                target_dto_kls.model_validate(lookup[k]) if k in lookup else None
                for k in keys
            ]

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

            async with session_factory() as session:
                stmt = select(target_orm_kls).where(
                    getattr(target_orm_kls, target_fk_col_name).in_(keys)
                )
                stmt = _apply_filters(stmt, filters)
                rows = (await session.scalars(stmt)).all()

            grouped = defaultdict(list)
            for row in rows:
                grouped[getattr(row, target_fk_col_name)].append(
                    target_dto_kls.model_validate(row)
                )

            return [grouped.get(k, []) for k in keys]

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "O2M"),
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

            async with session_factory() as session:
                join_stmt = select(secondary_table).where(
                    getattr(secondary_table.c, secondary_local_col_name).in_(keys)
                )
                join_rows = (await session.execute(join_stmt)).all()

                target_keys = list(
                    {_row_get(row, secondary_remote_col_name) for row in join_rows}
                )
                if not target_keys:
                    return [[] for _ in keys]

                target_stmt = select(target_orm_kls).where(
                    getattr(target_orm_kls, target_match_col_name).in_(target_keys)
                )
                target_stmt = _apply_filters(target_stmt, filters)
                target_rows = (await session.scalars(target_stmt)).all()

            target_map = {
                getattr(row, target_match_col_name): target_dto_kls.model_validate(row)
                for row in target_rows
            }

            grouped = defaultdict(list)
            for join_row in join_rows:
                target_obj = target_map.get(_row_get(join_row, secondary_remote_col_name))
                if target_obj is not None:
                    grouped[_row_get(join_row, secondary_local_col_name)].append(target_obj)

            return [grouped.get(k, []) for k in keys]

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_orm_kls, rel_name, "M2M"),
    )
