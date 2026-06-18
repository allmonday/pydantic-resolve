"""FromContext marker for UseCaseService method parameters."""

from __future__ import annotations

from typing import Annotated, Any, get_args, get_origin


class FromContext:
    """Marker annotation for parameters injected from MCP context_extractor.

    Used with ``Annotated`` to mark method parameters that should receive
    their values from the ``context_extractor`` callback rather than from
    the MCP tool's ``params`` JSON.

    This allows the same UseCaseService method to work seamlessly in both
    FastAPI (where the parameter is passed directly) and MCP (where it is
    extracted from request headers by ``context_extractor``).

    Usage::

        from typing import Annotated
        from pydantic_resolve.use_case import UseCaseService, FromContext

        class ProjectService(UseCaseService):
            @classmethod
            async def get_project(
                cls,
                user_id: Annotated[int, FromContext()],
                project_id: int,
            ) -> ProjectDetail:
                ...

    Consistent with other pydantic-resolve annotations:
    ``ExposeAs``, ``SendTo``, ``AutoLoad``.
    """

    pass


def is_from_context_annotation(annotation: Any) -> bool:
    """Return True if ``annotation`` is ``Annotated[..., FromContext()]``.

    False for None, missing annotations, and non-Annotated types —
    ``get_origin`` already returns None for those, so no explicit
    sentinel check is needed.
    """
    if get_origin(annotation) is not Annotated:
        return False
    return any(isinstance(arg, FromContext) for arg in get_args(annotation))
