"""FromContext marker for UseCaseService method parameters."""


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
