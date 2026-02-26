# Setup logging first (before any imports that might log)
from .utils.logger import setup_library_logger
from .utils.collector import Collector, ICollector, SendTo
from .utils.class_util import ensure_subset
from .utils.dataloader import build_list, build_object, copy_dataloader_kls
from .utils.conversion import mapper
from .exceptions import (
    ResolverTargetAttrNotFound,
    LoaderFieldNotProvidedError,
    MissingAnnotationError,
    GlobalLoaderFieldOverlappedError,
    MissingCollector)
from .resolver import Resolver
from .utils.depend import LoaderDepend, Loader
from .utils.subset import DefineSubset, SubsetConfig
from .utils.openapi import (
    model_config, serialization)
from .utils.er_diagram import Relationship, MultipleRelationship, Link, Entity, ErDiagram, LoadBy, base_entity
from .utils.resolver_configurator import config_resolver, config_global_resolver, reset_global_resolver
from .utils.expose import ExposeAs

# GraphQL 支持
# 分开导入，即使 graphql-core 未安装也能导入基础模块
try:
    from .graphql.query_decorator import query
except (ImportError, AttributeError):
    query = None

try:
    from .graphql.mutation_decorator import mutation
except (ImportError, AttributeError):
    mutation = None

try:
    from .graphql.types import FieldSelection, ParsedQuery
except (ImportError, AttributeError):
    FieldSelection = None
    ParsedQuery = None

try:
    from .graphql.exceptions import QueryParseError, GraphQLError
except (ImportError, AttributeError):
    QueryParseError = None
    GraphQLError = None

# 这些模块依赖 graphql-core，需要更仔细的导入处理
try:
    from .graphql.query_parser import QueryParser
except (ImportError, AttributeError):
    QueryParser = None

try:
    from .graphql.schema_builder import SchemaBuilder
except (ImportError, AttributeError):
    SchemaBuilder = None

try:
    from .graphql.response_builder import ResponseBuilder
except (ImportError, AttributeError):
    ResponseBuilder = None

try:
    from .graphql.handler import GraphQLHandler
except (ImportError, AttributeError):
    GraphQLHandler = None

setup_library_logger()

__all__ = [
    'Resolver',
    'LoaderDepend',
    'Loader',  # short 
    'Collector',
    'ICollector',
    'ExposeAs',
    'SendTo',

    'ResolverTargetAttrNotFound',
    'LoaderFieldNotProvidedError',
    'MissingAnnotationError',
    'GlobalLoaderFieldOverlappedError',
    'MissingCollector',

    'build_list',
    'build_object',
    'mapper',
    'ensure_subset',
    'model_config',
    'serialization',
    'copy_dataloader_kls',
    'DefineSubset',
    'SubsetConfig',

    'Entity',
    'Relationship',
    'MultipleRelationship',
    'Link',
    'ErDiagram',
    'LoadBy',
    'base_entity',

    'config_resolver',
    'config_global_resolver',
    'reset_global_resolver',

    # GraphQL 支持
    'query',
    'mutation',
    'GraphQLHandler',
    'QueryParser',
    'SchemaBuilder',
    'ResponseBuilder',
    'FieldSelection',
    'ParsedQuery',
    'QueryParseError',
    'GraphQLError',
]