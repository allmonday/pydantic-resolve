"""
GraphQL handler - coordinates all components and provides FastAPI integration.
"""

import inspect
import logging
import types
from typing import Any, Callable, Dict, ForwardRef, Optional, Tuple, Union, get_args, get_origin

from graphql import parse as parse_graphql
from graphql.language.ast import OperationDefinitionNode, OperationType

from pydantic_resolve.utils.er_diagram import ErDiagram
from pydantic_resolve.utils.resolver_configurator import config_resolver
from pydantic_resolve.graphql.exceptions import GraphQLError
from pydantic_resolve.graphql.executor import QueryExecutor
from pydantic_resolve.graphql.introspection import IntrospectionHelper
from pydantic_resolve.graphql.query_parser import QueryParser
from pydantic_resolve.graphql.response_builder import ResponseBuilder
from pydantic_resolve.graphql.schema_builder import SchemaBuilder

logger = logging.getLogger(__name__)


class GraphQLHandler:
    """
    GraphQL query handler

    Coordinates all components: parses queries, executes @query methods,
    builds response models, and resolves relationships.
    """

    def __init__(
        self,
        er_diagram: ErDiagram,
        enable_from_attribute_in_type_adapter: bool = False
    ):
        """
        Args:
            er_diagram: Entity relationship diagram
            enable_from_attribute_in_type_adapter: Enable Pydantic from_attributes mode for type adapter validation.
                Allows loaders to return Pydantic instances instead of dictionaries.
        """
        self.er_diagram = er_diagram
        self.enable_from_attribute_in_type_adapter = enable_from_attribute_in_type_adapter

        # Create diagram-specific resolver class
        self.resolver_class = config_resolver(
            name='GraphQLResolver',
            er_diagram=er_diagram
        )

        # Initialize components
        self.parser = QueryParser()
        self.builder = ResponseBuilder(
            er_diagram,
            resolver_class=self.resolver_class,
            enable_from_attribute_in_type_adapter=enable_from_attribute_in_type_adapter
        )
        self.schema_builder = SchemaBuilder(er_diagram)

        # Build query and mutation maps
        self.query_map = self._build_query_map()
        self.mutation_map = self._build_mutation_map()

        # Initialize helpers
        self.introspection = IntrospectionHelper(er_diagram, self.query_map, self.mutation_map)
        self.executor = QueryExecutor(
            parser=self.parser,
            builder=self.builder,
            resolver_class=self.resolver_class,
            enable_from_attribute_in_type_adapter=enable_from_attribute_in_type_adapter
        )

    def _build_query_map(self) -> Dict[str, Tuple[type, Callable]]:
        """
        Scan all entities and build query name to method mapping.

        Returns:
            Dictionary mapping query names to (return entity class, method) tuples
        """
        query_map = {}
        for entity_cfg in self.er_diagram.configs:
            methods = self.schema_builder._extract_query_methods(entity_cfg.kls)
            for method_info in methods:
                query_name = method_info['name']
                return_entity = self._extract_return_entity(method_info['method'])
                query_map[query_name] = (return_entity, method_info['method'])
        return query_map

    def _build_mutation_map(self) -> Dict[str, Tuple[type, Callable]]:
        """
        Scan all entities and build mutation name to method mapping.

        Returns:
            Dictionary mapping mutation names to (return entity class, method) tuples
        """
        mutation_map = {}
        for entity_cfg in self.er_diagram.configs:
            methods = self.schema_builder._extract_mutation_methods(entity_cfg.kls)
            for method_info in methods:
                mutation_name = method_info['name']
                return_entity = self._extract_return_entity(method_info['method'])
                mutation_map[mutation_name] = (return_entity, method_info['method'])
        return mutation_map

    def _extract_return_entity(self, method: Callable) -> Optional[type]:
        """
        Extract the return entity class from method's return type annotation.

        Handles:
        - List[Entity] -> Entity (first element)
        - Optional[List[Entity]] -> Entity (first element)
        - Optional[Entity] -> Entity
        - Entity -> Entity
        - Forward references are resolved using ERD lookup

        Args:
            method: @query decorated method

        Returns:
            Entity class if found, None otherwise
        """
        sig = inspect.signature(method)
        return_annotation = sig.return_annotation

        if return_annotation == inspect.Parameter.empty:
            return None

        origin = get_origin(return_annotation)

        # Unwrap Optional[List[T]] -> List[T] -> T
        if origin is list:
            args = get_args(return_annotation)
            if args:
                return_annotation = args[0]
                origin = get_origin(return_annotation)
        # Handle Optional[Entity] (Union[Entity, None]) - extract Entity
        elif origin is Union or (hasattr(types, 'UnionType') and isinstance(return_annotation, types.UnionType)):
            args = get_args(return_annotation)
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                return_annotation = non_none_args[0]
                # Check if it's Optional[List[T]]
                if get_origin(return_annotation) is list:
                    args = get_args(return_annotation)
                    if args:
                        return_annotation = args[0]

        # Handle ForwardRef
        if isinstance(return_annotation, ForwardRef):
            type_name = return_annotation.__forward_arg__
            for cfg in self.er_diagram.configs:
                if cfg.kls.__name__ == type_name:
                    return cfg.kls

        # Handle string annotation (from __future__ import annotations)
        if isinstance(return_annotation, str):
            for cfg in self.er_diagram.configs:
                if cfg.kls.__name__ == return_annotation:
                    return cfg.kls

        # Handle direct class reference
        if isinstance(return_annotation, type):
            return return_annotation

        return None

    async def execute(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query or mutation.

        Args:
            query: GraphQL query string

        Returns:
            GraphQL response format: {"data": {...}, "errors": [...]}
        """
        logger.debug(f"Executing GraphQL: {query[:100]}...")
        try:
            # Check for introspection query
            if self.introspection.is_introspection_query(query):
                logger.debug("Processing introspection query")
                return await self.introspection.execute(query)

            # Detect operation type (query or mutation)
            operation_type = self._detect_operation_type(query)

            if operation_type == 'mutation':
                logger.debug("Processing mutation")
                return await self.executor.execute_mutation(query, self.mutation_map)
            else:
                logger.debug("Processing query")
                return await self.executor.execute_query(query, self.query_map)

        except GraphQLError as e:
            logger.warning(f"GraphQL error: {e.message}")
            return {
                "data": None,
                "errors": [e.to_dict()]
            }
        except Exception as e:
            logger.exception("Unexpected error during GraphQL query execution")
            return {
                "data": None,
                "errors": [
                    {
                        "message": str(e),
                        "extensions": {"code": type(e).__name__}
                    }
                ]
            }

    def _detect_operation_type(self, query: str) -> str:
        """
        Detect operation type (query or mutation).

        Args:
            query: GraphQL query string

        Returns:
            'query' or 'mutation'
        """
        try:
            document = parse_graphql(query)
            for definition in document.definitions:
                if isinstance(definition, OperationDefinitionNode):
                    if definition.operation == OperationType.MUTATION:
                        return 'mutation'
                    return 'query'
        except Exception:
            # Keep default behavior on parse failure; actual parsing/validation
            # will happen in QueryExecutor with proper GraphQL error reporting.
            pass

        return 'query'
