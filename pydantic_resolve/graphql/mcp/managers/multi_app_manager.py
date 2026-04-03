"""Multi-app manager for MCP server.

This module provides the MultiAppManager class which manages multiple GraphQL applications,
each backed by an ErDiagram. It handles app registration, lookup, and routing.
"""

from typing import TYPE_CHECKING

from pydantic_resolve.graphql.handler import GraphQLHandler
from pydantic_resolve.graphql.schema.generators.introspection_generator import IntrospectionGenerator
from pydantic_resolve.graphql.schema.generators.sdl_builder import SDLBuilder
from pydantic_resolve.graphql.mcp.builders.introspection_query_helper import IntrospectionQueryHelper
from pydantic_resolve.graphql.mcp.managers.app_resources import AppResources
from pydantic_resolve.graphql.mcp.types.app_config import AppConfig

if TYPE_CHECKING:
    pass


class MultiAppManager:
    """Manages multiple GraphQL applications for MCP server.

    This manager handles:
    - Registration of multiple apps from AppConfig list
    - App lookup by name (with smart routing)
    - Resource creation for each app (Handler, IntrospectionQueryHelper, SDLBuilder)

    Each app is independent and backed by its own ErDiagram.
    """

    def __init__(self, apps: list[AppConfig]):
        """Initialize the manager with app configurations.

        Args:
            apps: List of AppConfig dictionaries, each containing:
                - name: Application name (required)
                - er_diagram: ErDiagram instance (required)
                - description: Application description (optional)
                - query_description: Query type description (optional)
                - mutation_description: Mutation type description (optional)

        Raises:
            ValueError: If an app with the same name already exists
        """
        self.apps: dict[str, AppResources] = {}
        self._app_names_lower: dict[str, str] = {}  # lowercase -> original case

        for app_config in apps:
            resources = self._create_app_resources(app_config)
            self._register_app(resources)

    def _create_app_resources(self, config: AppConfig) -> AppResources:
        """Create AppResources from AppConfig.

        This method:
        1. Creates a GraphQLHandler from the ErDiagram
        2. Creates an IntrospectionQueryHelper from introspection data
        3. Creates an SDLBuilder for schema generation

        Args:
            config: Application configuration

        Returns:
            AppResources instance with all components initialized
        """
        er_diagram = config.er_diagram
        name = config.name
        description = config.description or ""
        enable_from_attribute = config.enable_from_attribute_in_type_adapter

        # Create GraphQLHandler
        handler = GraphQLHandler(
            er_diagram=er_diagram,
            enable_from_attribute_in_type_adapter=enable_from_attribute,
        )

        # Create IntrospectionQueryHelper using IntrospectionGenerator
        introspection_generator = IntrospectionGenerator(
            er_diagram=er_diagram,
            query_map=handler.query_map,
            mutation_map=handler.mutation_map
        )
        introspection_data = introspection_generator.generate()
        entity_names = {cfg.kls.__name__ for cfg in er_diagram.entities}
        introspection_helper = IntrospectionQueryHelper(introspection_data, entity_names)

        # Create SDLBuilder
        sdl_builder = SDLBuilder(
            er_diagram=er_diagram,
        )

        return AppResources(
            name=name,
            description=description,
            handler=handler,
            introspection_helper=introspection_helper,
            sdl_builder=sdl_builder,
        )

    def _register_app(self, resources: AppResources) -> None:
        """Register an app's resources.

        Args:
            resources: AppResources to register

        Raises:
            ValueError: If an app with the same name already exists
        """
        name = resources.name
        name_lower = name.lower()

        if name_lower in self._app_names_lower:
            raise ValueError(f"App with name '{name}' already exists")

        self.apps[name] = resources
        self._app_names_lower[name_lower] = name

    def get_app(self, name: str) -> AppResources:
        """Get app resources by name.

        Supports smart routing:
        - Exact match: "MyApp" -> "MyApp"
        - Case-insensitive match: "myapp" -> "MyApp"

        Args:
            name: Application name

        Returns:
            AppResources for the matching app

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

        raise ValueError(f"App '{name}' not found. Available apps: {list(self.apps.keys())}")

    def list_apps(self) -> list[str]:
        """Get list of all registered app names.

        Returns:
            List of app names
        """
        return list(self.apps.keys())

    def get_app_info(self, name: str) -> dict:
        """Get detailed information about an app.

        Args:
            name: Application name

        Returns:
            Dictionary with app information:
                - name: App name
                - description: App description
                - query_count: Number of queries
                - mutation_count: Number of mutations
        """
        app = self.get_app(name)
        return {
            "name": app.name,
            "description": app.description,
            "query_count": len(app.query_names),
            "mutation_count": len(app.mutation_names),
        }
