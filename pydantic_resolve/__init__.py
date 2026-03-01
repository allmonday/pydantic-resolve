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
    MissingCollector)
from pydantic_resolve.resolver import Resolver
from pydantic_resolve.utils.depend import LoaderDepend, Loader
from pydantic_resolve.utils.subset import DefineSubset, SubsetConfig
from pydantic_resolve.utils.openapi import (
    model_config, serialization)
from pydantic_resolve.utils.er_diagram import Relationship, MultipleRelationship, Link, Entity, ErDiagram, LoadBy, base_entity, QueryConfig, MutationConfig
from pydantic_resolve.utils.resolver_configurator import config_resolver, config_global_resolver, reset_global_resolver
from pydantic_resolve.utils.expose import ExposeAs

# GraphQL support
from pydantic_resolve.graphql.decorator import query, mutation
from pydantic_resolve.graphql.schema_builder import SchemaBuilder
from pydantic_resolve.graphql.handler import GraphQLHandler

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
]