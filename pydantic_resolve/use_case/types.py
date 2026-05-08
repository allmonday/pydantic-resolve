"""UseCase MCP configuration types."""

from __future__ import annotations

from pydantic import BaseModel

from pydantic_resolve.use_case.business import UseCaseService


class UseCaseAppConfig(BaseModel):
    """Configuration for a UseCase application in MCP server.

    Attributes:
        name: Application name (required)
        services: List of UseCaseService subclasses for this app (required)
        description: Optional application description
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    services: list[type[UseCaseService]]
    description: str | None = None
