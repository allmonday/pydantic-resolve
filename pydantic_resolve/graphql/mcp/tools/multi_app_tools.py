"""Multi-app MCP tools for pydantic-resolve GraphQL.

This module provides MCP tools that implement progressive disclosure for GraphQL APIs.
The tools are organized in 4 layers:
- Layer 0: Application discovery (list_apps)
- Layer 1: Operation listing (list_queries, list_mutations)
- Layer 2: Schema details (get_query_schema, get_mutation_schema)
- Layer 3: Execution (graphql_query, graphql_mutation)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from pydantic_resolve.graphql.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from pydantic_resolve.graphql.mcp.managers.multi_app_manager import MultiAppManager


def register_multi_app_tools(mcp: "FastMCP", manager: "MultiAppManager") -> None:
    """Register all multi-app MCP tools with the FastMCP server.

    This function registers 7 tools that implement progressive disclosure:
    1. list_apps - Discover available applications
    2. list_queries - List query operations for an app
    3. list_mutations - List mutation operations for an app
    4. get_query_schema - Get detailed schema for a query
    5. get_mutation_schema - Get detailed schema for a mutation
    6. graphql_query - Execute a GraphQL query
    7. graphql_mutation - Execute a GraphQL mutation

    Args:
        mcp: The FastMCP server instance
        manager: The MultiAppManager instance containing app resources
    """

    # Layer 0: Application discovery
    @mcp.tool()
    def list_apps() -> Dict[str, Any]:
        """List all available GraphQL applications.

        Returns a list of all configured applications with their metadata:
        - name: Application name
        - description: Application description
        - queries_count: Number of query operations
        - mutations_count: Number of mutation operations

        IMPORTANT: All subsequent tool calls (except this one) require
        the app_name parameter. Choose an app_name from this list.

        Use this as the first step to discover what APIs are available,
        then use list_queries/list_mutations to explore specific operations.

        Returns:
            Dictionary with success status, app list, and usage hints

        Example response:
            {
                "success": true,
                "data": [{"name": "blog", "description": "Blog API", ...}],
                "hint": "Use 'blog' as app_name parameter..."
            }
        """
        try:
            apps_info = []
            for app in manager.apps.values():
                apps_info.append({
                    "name": app.name,
                    "description": app.description,
                    "queries_count": len(app.query_names),
                    "mutations_count": len(app.mutation_names),
                })

            # Add helpful hint about app_name usage
            app_names = [app["name"] for app in apps_info]
            hint = (
                f"IMPORTANT: All subsequent tool calls require app_name parameter. "
                f"Available apps: {app_names}. "
                f"Example: list_queries(app_name='{app_names[0] if app_names else 'app_name'}')"
            )

            return {
                "success": True,
                "data": apps_info,
                "hint": hint,
            }
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 1: List operations
    @mcp.tool()
    def list_queries(app_name: str) -> Dict[str, Any]:
        """List all available GraphQL queries for an application.

        Returns a lightweight list of query names and descriptions.
        Use this after list_apps to discover queries for a specific app,
        then use get_query_schema for detailed information.

        Args:
            app_name: Name of the application (required)

        Returns:
            Dictionary with query list and usage hints

        Example:
            list_queries(app_name="blog")
        """
        try:
            app = manager.get_app(app_name)
            queries = app.introspection_helper.list_operation_fields("Query")

            result = create_success_response(queries)
            result["hint"] = (
                f"Working with app '{app_name}'. "
                f"Use get_query_schema(name='<query_name>', app_name='{app_name}', response_type='sdl|introspection') "
                f"for detailed schema. response_type: 'sdl' (default, compact) or 'introspection' (detailed types). "
                f"Or use graphql_query to execute."
            )
            return result
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    @mcp.tool()
    def list_mutations(app_name: str) -> Dict[str, Any]:
        """List all available GraphQL mutations for an application.

        Returns a lightweight list of mutation names and descriptions.
        Use this after list_apps to discover mutations for a specific app,
        then use get_mutation_schema for detailed information.

        Args:
            app_name: Name of the application (required)

        Returns:
            Dictionary with mutation list and usage hints

        Example:
            list_mutations(app_name="blog")
        """
        try:
            app = manager.get_app(app_name)
            mutations = app.introspection_helper.list_operation_fields("Mutation")

            result = create_success_response(mutations)
            result["hint"] = (
                f"Working with app '{app_name}'. "
                f"Use get_mutation_schema(name='<mutation_name>', app_name='{app_name}', response_type='sdl|introspection') "
                f"for detailed schema. response_type: 'sdl' (default, compact) or 'introspection' (detailed types). "
                f"Or use graphql_mutation to execute."
            )
            return result
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 2: Get operation schema
    @mcp.tool()
    def get_query_schema(
        name: str, app_name: str, response_type: str = "sdl"
    ) -> Dict[str, Any]:
        """Get detailed schema information for a specific GraphQL query.

        Returns schema in two formats:
        - sdl: GraphQL Schema Definition Language (compact, AI-friendly)
        - introspection: Detailed introspection data with related types

        Args:
            name: Name of the query (e.g., "userEntityGetAll")
            app_name: Name of the application (required)
            response_type: Response format - "sdl" or "introspection" (default: "sdl")

        Returns:
            Dictionary with schema information

        Examples:
            get_query_schema(name="userEntityGetAll", app_name="blog", response_type="sdl")
            get_query_schema(name="userEntityGetAll", app_name="blog", response_type="introspection")
        """
        try:
            app = manager.get_app(app_name)

            if response_type == "sdl":
                sdl = app.sdl_builder.generate_operation_sdl(name, "Query")
                if sdl is None:
                    return create_error_response(
                        f"Query '{name}' not found in app '{app.name}'",
                        MCPErrors.OPERATION_NOT_FOUND,
                    )
                result = create_success_response({"sdl": sdl})
                result["hint"] = (
                    f"Ready to execute query on app '{app_name}'. "
                    f"Use graphql_query(query=..., app_name='{app_name}')"
                )
                return result

            # Introspection format
            operation = app.introspection_helper.get_operation_field("Query", name)
            if operation is None:
                return create_error_response(
                    f"Query '{name}' not found in app '{app.name}'",
                    MCPErrors.OPERATION_NOT_FOUND,
                )

            # Collect related types
            return_type = operation.get("type")
            related_type_names = app.introspection_helper.collect_related_types(return_type)
            types = app.introspection_helper.get_introspection_for_types(related_type_names)

            result = create_success_response({
                "operation": operation,
                "types": types,
            })
            result["hint"] = (
                f"Ready to execute query on app '{app_name}'. "
                f"Use graphql_query(query=..., app_name='{app_name}')"
            )
            return result
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    @mcp.tool()
    def get_mutation_schema(
        name: str, app_name: str, response_type: str = "sdl"
    ) -> Dict[str, Any]:
        """Get detailed schema information for a specific GraphQL mutation.

        Returns schema in two formats:
        - sdl: GraphQL Schema Definition Language (compact, AI-friendly)
        - introspection: Detailed introspection data with related types

        Args:
            name: Name of the mutation (e.g., "userEntityCreateUser")
            app_name: Name of the application (required)
            response_type: Response format - "sdl" or "introspection" (default: "sdl")

        Returns:
            Dictionary with schema information

        Examples:
            get_mutation_schema(name="userEntityCreateUser", app_name="blog", response_type="sdl")
        """
        try:
            app = manager.get_app(app_name)

            if response_type == "sdl":
                sdl = app.sdl_builder.generate_operation_sdl(name, "Mutation")
                if sdl is None:
                    return create_error_response(
                        f"Mutation '{name}' not found in app '{app.name}'",
                        MCPErrors.OPERATION_NOT_FOUND,
                    )
                return create_success_response({"sdl": sdl})

            # Introspection format
            operation = app.introspection_helper.get_operation_field("Mutation", name)
            if operation is None:
                return create_error_response(
                    f"Mutation '{name}' not found in app '{app.name}'",
                    MCPErrors.OPERATION_NOT_FOUND,
                )

            # Collect related types from return type
            return_type = operation.get("type")
            related_type_names = app.introspection_helper.collect_related_types(return_type)

            # Include argument types
            for arg in operation.get("args", []):
                arg_types = app.introspection_helper.collect_related_types(arg.get("type"))
                related_type_names.update(arg_types)

            types = app.introspection_helper.get_introspection_for_types(related_type_names)

            return create_success_response({
                "operation": operation,
                "types": types,
            })
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 3: Execute operations
    @mcp.tool()
    async def graphql_query(query: str, app_name: str) -> Dict[str, Any]:
        """Execute a GraphQL query on a specific application.

        Use this tool after discovering operations with list_queries and
        understanding their schema with get_query_schema.

        Args:
            query: A GraphQL query string
            app_name: Name of the application (required)

        Returns:
            Dictionary with query results or errors

        Examples:
            graphql_query(
                query="{ userEntityGetAll(limit: 10) { id name email } }",
                app_name="blog"
            )
        """
        if not query or not query.strip():
            return create_error_response(
                "query is required and cannot be empty",
                MCPErrors.MISSING_REQUIRED_FIELD,
            )

        try:
            app = manager.get_app(app_name)
            result = await app.handler.execute(query)

            if "errors" in result and result["errors"]:
                error_messages = [
                    err.get("message", "Unknown error") for err in result["errors"]
                ]
                error_response = create_error_response(
                    "; ".join(error_messages),
                    MCPErrors.QUERY_EXECUTION_ERROR,
                )
                error_response["hint"] = (
                    f"Error occurred on app '{app_name}'. "
                    f"Check your query syntax and field names."
                )
                return error_response

            # Success
            response = create_success_response(result.get("data"))
            response["hint"] = (
                f"Query executed on app '{app_name}'. "
                f"For future queries, remember to use app_name='{app_name}'."
            )
            return response
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    @mcp.tool()
    async def graphql_mutation(mutation: str, app_name: str) -> Dict[str, Any]:
        """Execute a GraphQL mutation on a specific application.

        Use this tool after discovering operations with list_mutations and
        understanding their schema with get_mutation_schema.

        Args:
            mutation: A GraphQL mutation string
            app_name: Name of the application (required)

        Returns:
            Dictionary with mutation results or errors

        Examples:
            graphql_mutation(
                mutation='mutation { userEntityCreateUser(name: "Alice", '
                        'email: "alice@example.com") { id name } }',
                app_name="blog"
            )
        """
        if not mutation or not mutation.strip():
            return create_error_response(
                "mutation is required and cannot be empty",
                MCPErrors.MISSING_REQUIRED_FIELD,
            )

        try:
            app = manager.get_app(app_name)
            result = await app.handler.execute(mutation)

            if "errors" in result and result["errors"]:
                error_messages = [
                    err.get("message", "Unknown error") for err in result["errors"]
                ]
                error_response = create_error_response(
                    "; ".join(error_messages),
                    MCPErrors.MUTATION_EXECUTION_ERROR,
                )
                error_response["hint"] = (
                    f"Error occurred on app '{app_name}'. "
                    f"Check your mutation syntax and field names."
                )
                return error_response

            # Success
            response = create_success_response(result.get("data"))
            response["hint"] = (
                f"Mutation executed on app '{app_name}'. "
                f"For future mutations, remember to use app_name='{app_name}'."
            )
            return response
        except ValueError as e:
            return create_error_response(str(e), MCPErrors.APP_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)
