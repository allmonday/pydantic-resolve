"""UseCaseService base class and BusinessMeta metaclass.

Provides the foundation for defining business service classes whose
async classmethods are automatically discovered and exposed via MCP.
"""

from __future__ import annotations

import asyncio
from typing import Any

USE_CASE_METHODS_ATTR = "__use_case_methods__"


class BusinessMeta(type):
    """Metaclass that collects async classmethod info for introspection.

    Scans the class namespace for async classmethods and stores them
    in ``__use_case_methods__`` for use by ServiceIntrospector.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Allow UseCaseService itself to be created without __use_case_methods__
        if name == "UseCaseService" and not any(
            isinstance(b, BusinessMeta) for b in bases
        ):
            setattr(cls, USE_CASE_METHODS_ATTR, {})
            return cls

        # Collect async classmethods from this class and bases
        methods: dict[str, Any] = {}

        # First collect from bases
        for base in bases:
            if hasattr(base, USE_CASE_METHODS_ATTR):
                methods.update(getattr(base, USE_CASE_METHODS_ATTR))

        # Then collect from current class
        _EXCLUDED_METHODS = {"get_tag_name"}
        for attr_name, attr_value in namespace.items():
            # Skip private/protected and excluded methods
            if attr_name.startswith("_") or attr_name in _EXCLUDED_METHODS:
                continue

            # Check if it's a classmethod wrapping an async function
            func = _unwrap_classmethod(attr_value)
            if func is not None and asyncio.iscoroutinefunction(func):
                methods[attr_name] = attr_value

        setattr(cls, USE_CASE_METHODS_ATTR, methods)
        return cls


def _unwrap_classmethod(value: Any) -> Any | None:
    """Unwrap a classmethod to get the underlying function, if any."""
    if isinstance(value, classmethod):
        return value.__func__
    return None


class UseCaseService(metaclass=BusinessMeta):
    """Base class for business service definitions.

    Subclasses define async classmethods that represent use case operations.
    The BusinessMeta metaclass automatically discovers these methods
    and makes them available for introspection.

    Example::

        class SprintService(UseCaseService):
            '''Sprint management service.'''

            @classmethod
            async def list_sprints(cls) -> list[SprintSummary]:
                '''Get all sprints.'''
                ...

            @classmethod
            async def get_sprint(cls, sprint_id: int) -> SprintSummary | None:
                '''Get a sprint by ID.'''
                ...
    """

    __use_case_methods__: dict[str, Any]

    @classmethod
    def get_tag_name(cls) -> str:
        """Return the tag name for this service.

        Returns the class name by default. Override to customize.
        """
        return cls.__name__
