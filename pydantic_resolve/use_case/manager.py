"""Multi-app manager for UseCase MCP server.

Manages multiple UseCase applications, each containing a group of UseCaseService
subclasses. Follows the same pattern as GraphQL MCP's MultiAppManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic_resolve.use_case.introspector import ServiceIntrospector
from pydantic_resolve.use_case.types import UseCaseAppConfig

if TYPE_CHECKING:
    from pydantic_resolve.use_case.business import UseCaseService


@dataclass
class UseCaseResources:
    """Container for all resources needed to serve a UseCase application via MCP.

    Attributes:
        name: Application name
        description: Application description
        introspector: ServiceIntrospector for method discovery
        services: Mapping of service name to service class
        context_extractor: Optional callback to extract request-scoped context
    """

    name: str
    description: str
    introspector: ServiceIntrospector
    services: dict[str, type["UseCaseService"]] = field(default_factory=dict)
    context_extractor: Callable[[Any], dict | Awaitable[dict]] | None = field(default=None)
    enable_mutation: bool = True

    @property
    def service_names(self) -> set[str]:
        """Get set of service names."""
        return set(self.services.keys())


class UseCaseManager:
    """Manages multiple UseCase applications for MCP server.

    This manager handles:
    - Registration of multiple apps from UseCaseAppConfig list
    - App lookup by name (with case-insensitive fallback)
    - Resource creation for each app (ServiceIntrospector, service mapping)

    Each app is independent and contains its own group of services.
    """

    def __init__(self, apps: list[UseCaseAppConfig]):
        """Initialize the manager with app configurations.

        Args:
            apps: List of UseCaseAppConfig instances.

        Raises:
            ValueError: If an app with the same name already exists
        """
        self.apps: dict[str, UseCaseResources] = {}
        self._app_names_lower: dict[str, str] = {}  # lowercase -> original case

        for app_config in apps:
            resources = self._create_app_resources(app_config)
            self._register_app(resources)

    def _create_app_resources(self, config: UseCaseAppConfig) -> UseCaseResources:
        """Create UseCaseResources from UseCaseAppConfig.

        Args:
            config: Application configuration

        Returns:
            UseCaseResources instance with introspector and service mapping
        """
        name = config.name
        description = config.description or ""
        services = config.services

        # Build service name -> class mapping
        service_map: dict[str, type[UseCaseService]] = {}
        for svc in services:
            service_map[svc.__name__] = svc

        # Create introspector for this app's services
        introspector = ServiceIntrospector(services)

        return UseCaseResources(
            name=name,
            description=description,
            introspector=introspector,
            services=service_map,
            context_extractor=config.context_extractor,
            enable_mutation=config.enable_mutation,
        )

    def _register_app(self, resources: UseCaseResources) -> None:
        """Register an app's resources.

        Args:
            resources: UseCaseResources to register

        Raises:
            ValueError: If an app with the same name already exists
        """
        name = resources.name
        name_lower = name.lower()

        if name_lower in self._app_names_lower:
            raise ValueError(f"App with name '{name}' already exists")

        self.apps[name] = resources
        self._app_names_lower[name_lower] = name

    def get_app(self, name: str) -> UseCaseResources:
        """Get app resources by name.

        Supports smart routing:
        - Exact match: "MyApp" -> "MyApp"
        - Case-insensitive match: "myapp" -> "MyApp"

        Args:
            name: Application name

        Returns:
            UseCaseResources for the matching app

        Raises:
            ValueError: If app not found
        """
        # Try exact match first
        if name in self.apps:
            return self.apps[name]

        # Try case-insensitive match
        name_lower = name.lower()
        if name_lower in self._app_names_lower:
            return self.apps[self._app_names_lower[name_lower]]

        raise ValueError(
            f"App '{name}' not found. Available apps: {list(self.apps.keys())}"
        )
