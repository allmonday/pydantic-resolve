"""
GraphQL query and mutation execution.

Handles the two-phase execution:
- Phase 1 (Serial): Method execution, model building, data transformation
- Phase 2 (Concurrent): Parallel execution of all root query Resolvers
"""

import asyncio
import inspect
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel

from pydantic_resolve.resolver import Resolver
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.types import get_core_types
from pydantic_resolve.graphql.exceptions import GraphQLError
from pydantic_resolve.graphql.query_parser import QueryParser
from pydantic_resolve.graphql.response_builder import ResponseBuilder

logger = logging.getLogger(__name__)


class QueryExecutor:
    """
    Handles GraphQL query and mutation execution.

    Implements two-phase execution:
    - Phase 1 (Serial): Query method execution, model building, data transformation
    - Phase 2 (Concurrent): Parallel execution of all root query Resolvers
    """

    def __init__(
        self,
        parser: QueryParser,
        builder: ResponseBuilder,
        resolver_class: type[Resolver],
        enable_from_attribute_in_type_adapter: bool = False
    ):
        """
        Args:
            parser: Query parser instance
            builder: Response builder instance
            resolver_class: Resolver class to use
            enable_from_attribute_in_type_adapter: Enable Pydantic from_attributes mode
        """
        self.parser = parser
        self.builder = builder
        self.resolver_class = resolver_class
        self.enable_from_attribute_in_type_adapter = enable_from_attribute_in_type_adapter

    async def execute_query(
        self,
        query: str,
        query_map: Dict[str, Tuple[type, Callable]]
    ) -> Dict[str, Any]:
        """
        Execute custom query with optimized two-phase execution:
        - Phase 1 (Serial): Query method execution, model building, data transformation
        - Phase 2 (Concurrent): Parallel execution of all root query Resolvers
        """
        logger.info("Starting custom query execution with concurrent optimization")

        # 1. Parse query
        parsed = self.parser.parse(query)
        logger.debug(f"Query parsed: {len(parsed.field_tree)} root fields found")

        # 2. Initialize results
        errors = []
        data = {}

        # ===== Phase 1: Serial Preparation =====
        logger.info("[Phase 1] Starting serial preparation phase")

        preparation_results = {}  # query_name -> (typed_data, is_list)

        for root_query_name, root_field_selection in parsed.field_tree.items():
            try:
                # Check if query exists
                if root_query_name not in query_map:
                    errors.append({
                        "message": f"Unknown query: {root_query_name}",
                        "extensions": {"code": "UNKNOWN_QUERY"}
                    })
                    logger.warning(f"[Phase 1] Unknown query: {root_query_name}")
                    continue

                entity, query_method = query_map[root_query_name]

                # Prepare query resolution
                typed_data, error_msg, error_dict = await self._prepare_query_resolution(
                    root_query_name=root_query_name,
                    root_field_selection=root_field_selection,
                    entity=entity,
                    query_method=query_method
                )

                if error_dict:
                    errors.append(error_dict)
                else:
                    # Store for Phase 2
                    is_list = isinstance(typed_data, list)
                    preparation_results[root_query_name] = (typed_data, is_list)

            except GraphQLError as e:
                errors.append(e.to_dict())
            except Exception as e:
                logger.exception(f"Unexpected error in Phase 1 for {root_query_name}")
                errors.append({
                    "message": str(e),
                    "extensions": {"code": type(e).__name__}
                })

        logger.info(f"[Phase 1] Completed: {len(preparation_results)} queries prepared, {len(errors)} errors")

        # ===== Phase 2: Concurrent Resolution =====
        logger.info("[Phase 2] Starting concurrent resolution phase")

        if preparation_results:
            # Build resolution tasks
            resolution_tasks = [
                (name, data, is_list)
                for name, (data, is_list) in preparation_results.items()
            ]

            # Execute all resolutions concurrently
            resolution_map = await self._execute_concurrent_resolutions(resolution_tasks)

            # Collect results and errors
            for query_name, (result_data, error_dict) in resolution_map.items():
                if error_dict:
                    errors.append(error_dict)
                else:
                    data[query_name] = result_data

        logger.info(f"[Phase 2] Completed: {len(data)} queries resolved successfully")

        # 3. Format response
        response = {
            "data": data if data else None,
            "errors": errors if errors else None
        }

        logger.info(f"Query execution complete: {len(data) if data else 0} successful, {len(errors) if errors else 0} errors")
        return response

    async def execute_mutation(
        self,
        query: str,
        mutation_map: Dict[str, Tuple[type, Callable]]
    ) -> Dict[str, Any]:
        """
        Execute custom mutation with two-phase execution:
        - Phase 1 (Serial): Mutation method execution, model building, data transformation
        - Phase 2 (Serial): Execute Resolver to resolve related data (each mutation executed sequentially)
        """
        logger.info("Starting custom mutation execution")

        # 1. Parse mutation
        parsed = self.parser.parse(query)
        logger.debug(f"Mutation parsed: {len(parsed.field_tree)} root fields found")

        # 2. Initialize results
        errors = []
        data = {}

        # ===== Phase 1 + Phase 2: Serial execution of each mutation =====
        logger.info("Starting serial mutation execution with two-phase resolution")

        for root_mutation_name, root_field_selection in parsed.field_tree.items():
            try:
                # Check if mutation exists
                if root_mutation_name not in mutation_map:
                    errors.append({
                        "message": f"Unknown mutation: {root_mutation_name}",
                        "extensions": {"code": "UNKNOWN_MUTATION"}
                    })
                    logger.warning(f"Unknown mutation: {root_mutation_name}")
                    continue

                entity, mutation_method = mutation_map[root_mutation_name]

                # === Phase 1: Execute mutation method ===
                args = root_field_selection.arguments or {}
                root_data = await self._execute_method(mutation_method, args, "mutation")
                logger.debug(f"Mutation method executed: {root_mutation_name}")

                # === Phase 1: Build response model ===
                response_model = self.builder.build_response_model(
                    entity=entity,
                    field_selection=root_field_selection
                )
                logger.debug(f"Response model built: {root_mutation_name}")

                # === Phase 1: Transform to response model ===
                if isinstance(root_data, list):
                    typed_data = [
                        response_model.model_validate(
                            d.model_dump() if hasattr(d, 'model_dump') else d
                        )
                        for d in root_data
                    ]
                elif root_data is not None:
                    typed_data = response_model.model_validate(
                        root_data.model_dump() if hasattr(root_data, 'model_dump') else root_data
                    )
                else:
                    typed_data = None

                logger.debug(f"Data transformed: {root_mutation_name}")

                # === Phase 2: Resolve related data ===
                if typed_data is not None:
                    resolver = self.resolver_class(enable_from_attribute_in_type_adapter=self.enable_from_attribute_in_type_adapter)

                    if isinstance(typed_data, list):
                        resolved = await resolver.resolve(typed_data)
                        data[root_mutation_name] = [r.model_dump(by_alias=True) for r in resolved] if resolved else []
                    else:
                        resolved = await resolver.resolve(typed_data)
                        data[root_mutation_name] = resolved.model_dump(by_alias=True) if resolved else None
                else:
                    data[root_mutation_name] = None

                logger.debug(f"Mutation resolved: {root_mutation_name}")

            except GraphQLError as e:
                errors.append(e.to_dict())
            except Exception as e:
                logger.exception(f"Unexpected error executing {root_mutation_name}")
                errors.append({
                    "message": str(e),
                    "extensions": {"code": type(e).__name__}
                })

        logger.info(f"Mutation execution complete: {len(data) if data else 0} successful, {len(errors) if errors else 0} errors")

        # 3. Format response
        response = {
            "data": data if data else None,
            "errors": errors if errors else None
        }

        return response

    async def _execute_method(
        self,
        method: Callable,
        arguments: Dict[str, Any],
        operation_type: str = "query"
    ) -> Any:
        """
        Execute @query or @mutation method

        Args:
            method: @query/@mutation decorated method (can be classmethod or regular function)
            arguments: Parameter dictionary
            operation_type: "query" or "mutation" for logging

        Returns:
            Method result
        """
        logger.debug(f"Executing {operation_type} method with arguments: {arguments}")
        try:
            # Convert arguments (handle BaseModel types)
            converted_args = self._convert_arguments(method, arguments)

            # schema_builder has extracted the underlying function (for classmethod it's __func__)
            # Call directly, passing None for first parameter (cls/self)
            return await method(None, **converted_args)
        except Exception as e:
            logger.error(f"{operation_type.capitalize()} method execution failed: {e}")
            raise GraphQLError(
                f"{operation_type.capitalize()} execution failed: {e}",
                extensions={"code": "EXECUTION_ERROR"}
            )

    def _convert_arguments(
        self,
        method: Callable,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert method parameters, transforming dict to corresponding Pydantic BaseModel instances

        Args:
            method: Method object
            arguments: Original parameter dictionary

        Returns:
            Converted parameter dictionary
        """
        converted = {}
        try:
            sig = inspect.signature(method)
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue

                if param_name not in arguments:
                    continue

                value = arguments[param_name]
                param_type = param.annotation

                # If parameter type is BaseModel and value is dict, convert
                if param_type != inspect.Parameter.empty:
                    core_types = get_core_types(param_type)
                    converted_value = None
                    for core_type in core_types:
                        if safe_issubclass(core_type, BaseModel):
                            if isinstance(value, dict):
                                converted_value = self._convert_to_model(value, core_type)
                                break
                            elif isinstance(value, list):
                                list_element_type = self._extract_list_element_type(param_type)
                                if list_element_type and safe_issubclass(list_element_type, BaseModel):
                                    converted_value = [
                                        self._convert_to_model(item, list_element_type) if isinstance(item, dict) else item
                                        for item in value
                                    ]
                                break
                    if converted_value is not None:
                        converted[param_name] = converted_value
                    else:
                        converted[param_name] = value
                else:
                    converted[param_name] = value

        except Exception as e:
            logger.warning(f"Failed to convert arguments: {e}")
            return arguments

        return converted

    def _convert_to_model(self, data: dict, model_class: type) -> BaseModel:
        """
        Recursively convert dict to Pydantic BaseModel instance

        Args:
            data: Dictionary data
            model_class: Target BaseModel class

        Returns:
            BaseModel instance
        """
        # Get all field types of the model
        try:
            type_hints = model_class.__annotations__
        except Exception:
            type_hints = {}

        converted_data = {}
        for field_name, field_value in data.items():
            if field_name in type_hints:
                field_type = type_hints[field_name]
                core_types = get_core_types(field_type)

                # Check if field type is BaseModel
                is_model_field = False
                for core_type in core_types:
                    if safe_issubclass(core_type, BaseModel):
                        if isinstance(field_value, dict):
                            converted_data[field_name] = self._convert_to_model(field_value, core_type)
                        elif isinstance(field_value, list):
                            converted_data[field_name] = [
                                self._convert_to_model(item, core_type) if isinstance(item, dict) else item
                                for item in field_value
                            ]
                        else:
                            converted_data[field_name] = field_value
                        is_model_field = True
                        break

                if not is_model_field:
                    converted_data[field_name] = field_value
            else:
                converted_data[field_name] = field_value

        return model_class(**converted_data)

    def _extract_list_element_type(self, field_type: Any) -> Optional[type]:
        """
        Extract element type T from list[T]

        Args:
            field_type: Field type (possibly list[T])

        Returns:
            Element type, or None if not a list
        """
        from typing import get_args, get_origin

        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args:
                return args[0]
        return None

    async def _prepare_query_resolution(
        self,
        root_query_name: str,
        root_field_selection: Any,
        entity: type,
        query_method: Callable
    ) -> Tuple[Optional[Any], Optional[str], Optional[Dict]]:
        """
        Prepare query resolution (Phase 1: Serial)

        Args:
            root_query_name: Root query field name
            root_field_selection: Parsed field selection
            entity: Entity class
            query_method: @query decorated method

        Returns:
            Tuple of (typed_data, error_message, error_dict)
            - Success: (typed_data, None, None)
            - Failure: (None, error_message, error_dict)
        """
        logger.debug(f"[Phase 1] Preparing query: {root_query_name}")

        try:
            # 1. Execute query method
            args = root_field_selection.arguments or {}
            root_data = await self._execute_method(query_method, args, "query")
            logger.debug(f"[Phase 1] Query method executed: {root_query_name}")

            # 2. Build response model
            response_model = self.builder.build_response_model(
                entity=entity,
                field_selection=root_field_selection
            )
            logger.debug(f"[Phase 1] Response model built: {root_query_name}")

            # 3. Transform to response model
            if isinstance(root_data, list):
                typed_data = [
                    response_model.model_validate(
                        d.model_dump() if hasattr(d, 'model_dump') else d
                    )
                    for d in root_data
                ]
            elif root_data is not None:
                typed_data = response_model.model_validate(
                    root_data.model_dump() if hasattr(root_data, 'model_dump') else root_data
                )
            else:
                typed_data = None

            logger.debug(f"[Phase 1] Data transformed: {root_query_name}")
            return typed_data, None, None

        except GraphQLError as e:
            logger.warning(f"[Phase 1] GraphQL error preparing {root_query_name}: {e.message}")
            return None, e.message, e.to_dict()
        except Exception as e:
            logger.exception(f"[Phase 1] Unexpected error preparing {root_query_name}")
            error_dict = {
                "message": str(e),
                "extensions": {"code": type(e).__name__}
            }
            return None, str(e), error_dict

    async def _resolve_query_data(
        self,
        root_query_name: str,
        typed_data: Any,
        is_list: bool
    ) -> Tuple[Optional[Any], Optional[Dict]]:
        """
        Resolve query data (Phase 2: Concurrent)

        Args:
            root_query_name: Root query field name
            typed_data: Typed Pydantic data
            is_list: Whether data is a list

        Returns:
            Tuple of (result_data, error_dict)
            - Success: (result_data, None)
            - Failure: (None, error_dict)
        """
        logger.debug(f"[Phase 2] Resolving query: {root_query_name}")

        try:
            result_data = None

            if typed_data is not None:
                resolver = self.resolver_class(enable_from_attribute_in_type_adapter=self.enable_from_attribute_in_type_adapter)

                if is_list:
                    result = await resolver.resolve(typed_data)
                    if result is not None:
                        result_data = [r.model_dump(by_alias=True) for r in result]
                    else:
                        result_data = []
                else:
                    result = await resolver.resolve(typed_data)
                    if result is not None:
                        result_data = result.model_dump(by_alias=True)
                    else:
                        result_data = None
            else:
                result_data = [] if is_list else None

            logger.debug(f"[Phase 2] Query resolved: {root_query_name}")
            return result_data, None

        except Exception as e:
            logger.exception(f"[Phase 2] Error resolving {root_query_name}")
            error_dict = {
                "message": f"Resolution failed for {root_query_name}: {str(e)}",
                "extensions": {"code": type(e).__name__}
            }
            return None, error_dict

    async def _execute_concurrent_resolutions(
        self,
        resolution_tasks: List[Tuple[str, Any, bool]]
    ) -> Dict[str, Tuple[Optional[Any], Optional[Dict]]]:
        """
        Execute multiple query resolutions concurrently, using semaphore to control concurrency

        Args:
            resolution_tasks: List of (query_name, typed_data, is_list) tuples

        Returns:
            Dict mapping query_name to (result_data, error_dict)
        """
        if not resolution_tasks:
            return {}

        logger.info(f"[Phase 2] Starting concurrent resolution of {len(resolution_tasks)} queries")

        # Resource control: Only limit concurrent Resolver instances if user explicitly sets environment variable
        max_concurrency_str = os.getenv("PYDANTIC_RESOLVE_MAX_CONCURRENT_QUERIES")
        if max_concurrency_str:
            max_concurrency = int(max_concurrency_str)
            semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else None
        else:
            semaphore = None

        async def resolve_with_semaphore(query_name: str, typed_data: Any, is_list: bool):
            if semaphore:
                async with semaphore:
                    return await self._resolve_query_data(query_name, typed_data, is_list)
            else:
                return await self._resolve_query_data(query_name, typed_data, is_list)

        # Execute all resolution tasks concurrently
        results = await asyncio.gather(
            *[resolve_with_semaphore(name, data, is_list) for name, data, is_list in resolution_tasks],
            return_exceptions=True
        )

        # Process results and map to query names
        query_names = [name for name, _, _ in resolution_tasks]
        resolution_map = {}

        for query_name, result in zip(query_names, results):
            if isinstance(result, Exception):
                logger.exception(f"[Phase 2] Unexpected exception for {query_name}")
                error_dict = {
                    "message": f"Unexpected error: {str(result)}",
                    "extensions": {"code": type(result).__name__}
                }
                resolution_map[query_name] = (None, error_dict)
            else:
                resolution_map[query_name] = result

        logger.info("[Phase 2] Completed concurrent resolution")
        return resolution_map
