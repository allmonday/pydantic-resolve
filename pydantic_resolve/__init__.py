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
from .utils.er_diagram import Relationship, MultipleRelationship, Link, Entity, ErDiagram, LoadBy, base_entity, QueryConfig, MutationConfig
from .utils.resolver_configurator import config_resolver, config_global_resolver, reset_global_resolver
from .utils.expose import ExposeAs

# GraphQL support
from .graphql.decorator import query, mutation
from .graphql.schema_builder import SchemaBuilder
from .graphql.handler import GraphQLHandler

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