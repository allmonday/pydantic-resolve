"""Utilities for scanning Pydantic field ``Annotated`` metadata.

Pydantic pre-extracts ``Annotated[T, marker, ...]`` metadata into
``model_fields[name].metadata`` at class creation time. Markers used
across the project: ``ExposeAs`` (alias for descendant resolve),
``SendTo`` (collector routing), ``AutoLoad`` (explicit relationship
loader), and ``FromContext`` (server-injected method params — handled
separately because it appears on method signatures, not model fields).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel


def iter_fields_with_marker(
    model_cls: type[BaseModel],
    marker_cls: type,
) -> Iterator[tuple[str, Any, Any]]:
    """Yield ``(field_name, field_info, marker_instance)`` for each field
    on ``model_cls`` whose ``Annotated`` metadata contains an instance
    of ``marker_cls``.

    Used by the ``ExposeAs`` / ``SendTo`` / ``AutoLoad`` scanners to find
    fields carrying their respective markers. Centralizes the
    ``model_fields[name].metadata`` iteration so each scanner only has
    to declare its marker class.

    Args:
        model_cls: A Pydantic ``BaseModel`` subclass.
        marker_cls: The marker class to look for in field metadata
            (e.g. ``ExposeInfo``, ``SendToInfo``, ``LoaderInfo``).

    Yields:
        ``(field_name, field_info, marker_instance)`` for each match.
        ``field_info`` is the ``pydantic.fields.FieldInfo`` (carries
        ``.annotation``, ``.default``, etc.); ``marker_instance`` is the
        actual marker found (already known to be an instance of
        ``marker_cls``).
    """
    for name, field_info in model_cls.model_fields.items():
        for meta in field_info.metadata:
            if isinstance(meta, marker_cls):
                yield name, field_info, meta


__all__ = ["iter_fields_with_marker"]
