"""UseCase MCP configuration types."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from pydantic_resolve.use_case.business import UseCaseService


class UseCaseAppConfig(BaseModel):
    """Configuration for a UseCase application in MCP server.

    Attributes:
        name: Application name (required)
        services: List of UseCaseService subclasses for this app (required)
        description: Optional application description
        enable_mutation: Whether mutation methods are exposed via MCP (default: True).
            When False, mutation methods are hidden from list_services,
            describe_service, and call_use_case tools.
        context_extractor: Optional callback that extracts request-scoped context
            (e.g. user identity from Authorization header). Receives the FastMCP
            Context object and returns a dict injected as ``_context`` parameter
            into UseCaseService methods. Can be sync or async.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    services: list[type[UseCaseService]]
    description: str | None = None
    enable_mutation: bool = True
    context_extractor: Callable[[Any], dict | Awaitable[dict]] | None = None
