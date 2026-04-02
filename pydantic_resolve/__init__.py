# Setup logging first (before any imports that might log)
from pydantic_resolve.utils.logger import setup_library_logger
from pydantic_resolve.utils.collector import Collector, ICollector, SendTo
from pydantic_resolve.utils.class_util import ensure_subset
from pydantic_resolve.utils.dataloader import build_list, build_object, copy_dataloader_kls
from pydantic_resolve.utils.conversion import mapper
from pydantic_resolve.exceptions import (
    ResolverTargetAttrNotFound,
    LoaderFieldNotProvidedError,
    MissingAnnotationError,
    GlobalLoaderFieldOverlappedError,
    MissingCollector,
    LoaderContextNotProvidedError)
from pydantic_resolve.resolver import Resolver
from pydantic_resolve.utils.depend import Loader
from pydantic_resolve.utils.subset import DefineSubset, SubsetConfig
from pydantic_resolve.utils.openapi import (
    serialization)
from pydantic_resolve.utils.er_diagram import Relationship, Entity, ErDiagram, base_entity, QueryConfig, MutationConfig
from pydantic_resolve.utils.resolver_configurator import config_resolver, config_global_resolver, reset_global_resolver
from pydantic_resolve.utils.expose import ExposeAs

# GraphQL support
from pydantic_resolve.graphql.decorator import query, mutation
from pydantic_resolve.graphql.schema_builder import SchemaBuilder
from pydantic_resolve.graphql.handler import GraphQLHandler

# MCP (optional - requires pydantic-resolve[mcp])
try:
    from pydantic_resolve.graphql.mcp.server import create_mcp_server, MultiAppManager, register_multi_app_tools
    from pydantic_resolve.graphql.mcp.types.app_config import AppConfig
except ImportError:
    pass


setup_library_logger()

__all__ = [
    'Resolver',
    'Loader',
    'Collector',
    'ICollector',
    'ExposeAs',
    'SendTo',

    # errors
    'ResolverTargetAttrNotFound',
    'LoaderFieldNotProvidedError',
    'MissingAnnotationError',
    'GlobalLoaderFieldOverlappedError',
    'MissingCollector',
    'LoaderContextNotProvidedError',

    # utils
    'build_list',
    'build_object',
    'mapper',
    'serialization',
    'copy_dataloader_kls',

    # subset
    'ensure_subset',
    'DefineSubset',
    'SubsetConfig',

    # ER diagram
    'Entity',
    'Relationship',
    'ErDiagram',
    'base_entity',
    'QueryConfig',
    'MutationConfig',

    'config_resolver',
    'config_global_resolver',
    'reset_global_resolver',

    # GraphQL support
    'query',
    'mutation',
    'GraphQLHandler',
    'SchemaBuilder',

    # MCP
    'create_mcp_server',  # lightweight MCP server wrapper
    'AppConfig',
    'MultiAppManager',
    'register_multi_app_tools',
]