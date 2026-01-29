import copy
import inspect
from typing import TypedDict
from inspect import isfunction
from collections import defaultdict
from pydantic import BaseModel
import pydantic_resolve.constant as const
import pydantic_resolve.utils.class_util as class_util
from pydantic_resolve.utils.collector import ICollector, pre_generate_collector_config
from pydantic_resolve.utils.depend import Depends
from pydantic_resolve.utils.er_diagram import ErLoaderPreGenerator
from pydantic_resolve.exceptions import ResolverTargetAttrNotFound, MissingCollector
from pydantic_resolve.utils.expose import pre_generate_expose_config

# ====================
# Types
# ====================
class FieldContext(TypedDict):
    """Context containing field-related information during analysis.

    This context groups all field-related data extracted during the class preparation phase,
    reducing the number of variables that need to be passed between methods.
    """
    # All pydantic field names in the class
    all_fields: set

    # List of (field_name, types) tuples for fields that are objects (BaseModel instances)
    # Example: [('user', [User]), ('items', [Item])]
    object_fields: list

    # Dictionary mapping field names to their types
    # Example: {'user': User, 'items': list[Item]}
    object_field_pairs: dict

    # List of resolve_ method names (e.g., ['resolve_user', 'resolve_items'])
    resolve_fields: list[str]

    # List of post_ method names (e.g., ['post_total', 'post_formatted_name'])
    post_fields: list[str]

    # Set of field names that have a resolve_ method (without the 'resolve_' prefix)
    # Example: {'user', 'items'}
    fields_with_resolver: set

    # List of object field names that do NOT have a resolve_ method
    # These fields will be traversed recursively without special handling
    object_fields_without_resolver: list[str]

    # Expose configuration: which fields to expose to descendant nodes
    # Format: {field_name: alias_name}
    expose_dict: dict

    # Collect configuration: which fields to collect from descendant nodes
    # Format: {field_name: collector_alias or list of collector_aliases}
    collect_dict: dict


class MethodContext(TypedDict):
    """Context containing method scan results during analysis.

    This context groups the results of scanning resolve_ and post_ methods,
    including their parameters, dependencies, and configuration.
    """
    # Dictionary mapping resolve_ method names to their scanned parameters
    # Keys: method names (e.g., 'resolve_user')
    # Values: ResolveMethodType with context, parent, dataloaders info
    resolve_params: dict

    # Dictionary mapping post_ method names to their scanned parameters
    # Keys: method names (e.g., 'post_total')
    # Values: PostMethodType with context, parent, dataloaders, collectors info
    post_params: dict

    # Scanned parameters for the special post_default_handler method
    # Contains context, parent, collectors info if the method exists
    post_default_handler_params: 'PostDefaultHandlerType | None'

    # Whether any resolve_ or post_ method requests the context parameter
    # Used to optimize context propagation
    has_context: bool

class DataLoaderType(TypedDict):
    param: str
    kls: type
    path: str
    request_type: list[type]

class CollectorType(TypedDict):
    field: str 
    param: str
    instance: object
    alias: str
    
class ResolveMethodType(TypedDict):
    trim_field: str
    context: bool
    parent: bool
    ancestor_context: bool
    dataloaders: list[DataLoaderType]

class PostMethodType(TypedDict):
    trim_field: str
    context: bool
    parent: bool
    ancestor_context: bool
    dataloaders: list[DataLoaderType]
    collectors: list[CollectorType] 

class PostDefaultHandlerType(TypedDict):
    context: bool
    parent: bool
    ancestor_context: bool
    collectors: list[CollectorType]

class KlsMetaType(TypedDict):
    """Complete metadata for a Pydantic model class.

    This TypedDict stores all extracted information about a Pydantic model class,
    including its resolve/post methods, field configurations, and traversal state.

    This is the final output stored in metadata[kls_name] after analysis completes.
    """
    # List of resolve_ method names (e.g., ['resolve_user', 'resolve_items'])
    # These methods fetch related data for their respective fields
    resolve: list[str]

    # List of post_ method names (e.g., ['post_total', 'post_formatted_name'])
    # These methods transform or compute data after all resolves complete
    post: list[str]

    # Detailed parameters for each resolve_ method
    # Keys: method names (e.g., 'resolve_user')
    # Values: ResolveMethodType containing context, parent, ancestor_context, dataloaders
    resolve_params: dict[str, ResolveMethodType]

    # Detailed parameters for each post_ method
    # Keys: method names (e.g., 'post_total')
    # Values: PostMethodType containing context, parent, ancestor_context, dataloaders, collectors
    post_params: dict[str, PostMethodType]

    # Parameters for the special post_default_handler method
    # This method is called for fields that don't have a specific post_ method
    # Contains context, parent, collectors info if the method exists, None otherwise
    post_default_handler_params: PostDefaultHandlerType | None

    # Object field names that do NOT have a resolve_ method
    # These are fields that are Pydantic objects but will be traversed without special handling
    # "raw" means they are stored as-is without resolution logic
    # Example: ['profile', 'settings'] for fields that are just BaseModel objects
    raw_object_fields: list[str]

    # Object field names that need to be traversed
    # This list is dynamically populated during traversal based on ancestor requirements
    # If a parent class needs to access a child's data, that field is added here
    # Example: If a parent post_ method accesses child.user, 'user' will be in this list
    object_fields: list[str]

    # Expose configuration: which fields to expose to descendant nodes
    # Format: {field_name: alias_name}
    # Example: {'name': 'parent_name', 'id': 'parent_id'}
    # Descendant nodes can access exposed data via ancestor_context parameter
    expose_dict: dict

    # Collect configuration: which fields to collect from descendant nodes
    # Format: {field_name: collector_alias or list of collector_aliases}
    # Example: {'id': 'id_collector', ('name', 'email'): ['contact_collector', 'validation_collector']}
    # Collectors gather data from child nodes and make it available to parent post_ methods
    collect_dict: dict

    # The actual Pydantic model class
    # Used to instantiate objects and access class attributes
    # Example: <class 'app.models.User'>
    kls: type

    # Whether any resolve_ or post_ method in this class requires the context parameter
    # Used to optimize context propagation - if False, context won't be passed to instances
    # This is a performance optimization to avoid unnecessary context variable operations
    has_context: bool

    # Whether this class needs to be traversed during resolution
    # If True, this class will be visited even if no direct field accesses it
    # This is set when descendant nodes require any pydantic-resolve related operations, it's ancestors should traverse to it.
    should_traverse: bool

class LoaderQueryMeta(TypedDict):
    required_types: list
    fields: list[str]

# kls_name -> KlsMetaType
MetaType = dict[str, KlsMetaType]  

class MappedMetaMemberType(KlsMetaType):
    """Extended metadata with class path and collector prototype map.

    This extends KlsMetaType with additional fields needed for runtime resolution,
    including the path to the class and the prototype map for collector instances.
    """
    # Full path of the class (e.g., 'app.models.User')
    # Used to generate unique signatures for collectors
    kls_path: str

    # Prototype map for collector instances
    # Structure: {collector_alias: {(kls_path, field, param): collector_instance}}
    #
    # This is a template that stores all collector instances defined in post_ methods.
    # Each collector is identified by a unique signature tuple:
    # - kls_path: full class path where the collector is defined
    # - field: the post_ method name (e.g., 'post_total')
    # - param: the parameter name in the method signature
    #
    # Why "proto"? This is a prototype template that gets deep-copied for each
    # object instance during resolution, ensuring each object has its own isolated
    # collector instance to avoid data contamination between objects.
    #
    # Example:
    #   {
    #     'contact_info': {
    #       ('app.models.Comment', 'owner', 'collector'): <Collector instance>
    #     }
    #   }
    #
    # Usage flow:
    #   1. Created during analysis phase by _calc_alias_map_from_collectors()
    #   2. Deep-copied during resolution by generate_alias_map_with_cloned_collector()
    #   3. Used to collect data from child nodes and pass to parent post_ methods
    alias_map_proto: dict[str, dict[tuple[str, str, str], object]]

MappedMetaType = dict[type, MappedMetaMemberType]


# ====================
# Utility functions
# ====================

def _has_config(info: KlsMetaType) -> bool:
    """Check if a class has any configuration that requires traversal.

    Args:
        info: Metadata for a Pydantic model class

    Returns:
        True if the class has resolve/post methods, expose/collect configs,
        or a post_default_handler
    """
    return (
        len(info['resolve']) > 0 or
        len(info['post']) > 0 or
        len(info['collect_dict']) > 0 or
        len(info['expose_dict']) > 0 or
        info['post_default_handler_params'] is not None
    )


def _get_all_fields_and_object_fields(kls: type) -> tuple:
    """Extract all fields and object fields from a Pydantic model.

    Args:
        kls: Pydantic model class

    Returns:
        Tuple of (all_fields, object_fields, object_field_pairs)
        - all_fields: set of all field names
        - object_fields: list of (field_name, types) tuples
        - object_field_pairs: dict mapping field names to types

    Raises:
        TypeError: if kls is not a Pydantic BaseModel
    """
    if class_util.safe_issubclass(kls, BaseModel):
        all_fields = set(class_util.get_pydantic_field_keys(kls))
        object_fields = list(class_util.get_pydantic_fields(kls))
    else:
        raise TypeError('invalid type: should be pydantic object')
    return all_fields, object_fields, {k: v for k, v in object_fields}


def _has_post_default_handler(kls: type) -> bool:
    """Check if a class has a post_default_handler method.

    Args:
        kls: Class to check

    Returns:
        True if the class has a post_default_handler method
    """
    fields = dir(kls)
    fields = [f for f in fields if f == const.POST_DEFAULT_HANDLER and isfunction(getattr(kls, f))]
    return len(fields) > 0


def _get_resolve_and_post_fields(kls: type) -> tuple:
    """Extract resolve_ and post_ method names from a class.

    Args:
        kls: Class to scan

    Returns:
        Tuple of (resolve_fields, post_fields, fields_with_resolver)
        - resolve_fields: list of resolve_ method names
        - post_fields: list of post_ method names
        - fields_with_resolver: set of field names with resolve_ methods
    """
    fields = dir(kls)

    resolve_fields = [f for f in fields if f.startswith(const.RESOLVE_PREFIX) and isfunction(getattr(kls, f))]
    post_fields = [
        f for f in fields if f.startswith(const.POST_PREFIX)
        and f != const.POST_DEFAULT_HANDLER
        and isfunction(getattr(kls, f))
    ]
    fields_with_resolver = {field.replace(const.RESOLVE_PREFIX, '') for field in resolve_fields}
    return resolve_fields, post_fields, fields_with_resolver


def _validate_resolve_and_post_fields(resolve_fields: list, post_fields: list, all_fields: set):
    """Validate that resolve_ and post_ methods have corresponding fields.

    Args:
        resolve_fields: List of resolve_ method names
        post_fields: List of post_ method names
        all_fields: Set of all field names in the class

    Raises:
        ResolverTargetAttrNotFound: if a resolve/post method doesn't have a corresponding field
    """
    for field in resolve_fields:
        resolve_field = field.replace(const.RESOLVE_PREFIX, '')
        if resolve_field not in all_fields:
            raise ResolverTargetAttrNotFound(f"attribute {resolve_field} not found")

    for field in post_fields:
        post_field = field.replace(const.POST_PREFIX, '')
        if post_field not in all_fields:
            raise ResolverTargetAttrNotFound(f"attribute {post_field} not found")


# ====================
# Method scanning functions
# ====================

def _scan_resolve_method(method, field: str, request_types: list[type]) -> ResolveMethodType:
    result: ResolveMethodType = {
        'trim_field': field.replace(const.RESOLVE_PREFIX, ''),
        'context': False,
        'parent': False,
        'ancestor_context': False,
        'dataloaders': []  # collect func or class, do not create instance
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True

    if signature.parameters.get('parent'):
        result['parent'] = True

    for name, param in signature.parameters.items():
        if isinstance(param.default, Depends):
            info: DataLoaderType = { 
                'param': name,
                'kls': param.default.dependency,  # for later initialization
                'path': class_util.get_kls_full_name(param.default.dependency),
                'request_type': request_types
            }
            result['dataloaders'].append(info)

    for name, param in signature.parameters.items():
        if isinstance(param.default, ICollector):
            raise AttributeError("Collector is not available in resolve_method")

    return result


def _scan_post_method(method, field: str, request_types: list[type]) -> PostMethodType:
    result: PostMethodType = {
        'trim_field': field.replace(const.POST_PREFIX, ''),
        'context': False,
        'ancestor_context': False,
        'parent': False,
        'dataloaders': [],
        'collectors': []
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True

    if signature.parameters.get('parent'):
        result['parent'] = True

    
    for name, param in signature.parameters.items():
        if isinstance(param.default, Depends):
            loader_info: DataLoaderType = { 
                'param': name,
                'kls': param.default.dependency,  # for later initialization
                'path': class_util.get_kls_full_name(param.default.dependency),
                'request_type': request_types
            }
            result['dataloaders'].append(loader_info)

        if isinstance(param.default, ICollector):
            info: CollectorType = {
                'field': field,
                'param': name,
                'instance': param.default,
                'alias': param.default.alias 
            }
            result['collectors'].append(info)

            
    return result


def _scan_post_default_handler(method) -> PostDefaultHandlerType:
    result: PostDefaultHandlerType = {
        'context': False,
        'ancestor_context': False,
        'parent': False,
        'collectors': []
    }
    signature = inspect.signature(method)

    if signature.parameters.get('context'):
        result['context'] = True

    if signature.parameters.get('ancestor_context'):
        result['ancestor_context'] = True

    if signature.parameters.get('parent'):
        result['parent'] = True

    for name, param in signature.parameters.items():
        if isinstance(param.default, ICollector):
            info: CollectorType = {
                'field': const.POST_DEFAULT_HANDLER,
                'param': name,
                'instance': param.default,
                'alias': param.default.alias 
            }
            result['collectors'].append(info)

    return result


# =======================
# Main entry
# =======================
class Analytic:
    """
    Analyze pydantic models to extract metadata for resolution.

    This class traverses the pydantic model tree to collect:
    - resolve methods
    - post methods
    - expose configurations
    - collector configurations
    - object fields that need traversal
    """
    def __init__(self, er_pre_generator: ErLoaderPreGenerator | None=None) -> None:
        self.expose_set = set()
        self.collect_set = set()
        self.metadata: MetaType = {}
        self.er_pre_generator = er_pre_generator

    def _validate_expose(self, expose_dict: dict, kls_name: str):
        if not isinstance(expose_dict, dict):
            raise TypeError(f'{const.EXPOSE_TO_DESCENDANT} is not dict')
        for _, v in expose_dict.items():
            if v in self.expose_set:
                raise ValueError(f'Expose alias name conflicts, please check: {kls_name}')
            self.expose_set.add(v)

    def _add_collector_info(self, post_params):
        """
        add collector alias during _walker (breadth first traversal)
        so that it should ensure the definition of collector is always before usage
        which means collector should always be defined before ancestor nodes actually send data.
        """
        for _, param in post_params.items():
            for collector in param['collectors']:
                self.collect_set.add(collector['alias'])

    def _add_collector_info_for_default_handler(self, post_default_params):
        """
        same like _add_collector_info
        """
        if post_default_params is not None:
            for collector in post_default_params['collectors']:
                self.collect_set.add(collector['alias'])

    def _validate_collector(self, collect_dict: dict, kls_name: str):
        """
        validate if the collector is declared in ancestor nodes.

        available format of `__pydantic_resolve_collect__`

        class A(BaseModel):
            __pydantic_resolve_collect__ = {
                'name': 'collector_a',                                  # send name to collector_a
                ('name', 'age'): 'collector_b',                         # send ('name', 'age') to collector_b
                'name': ('collector_c', 'collector_d'),                 # send name to both collector_c and d
                ('name', 'age'): ('collector_e', 'collector_f'),        # send ('name', 'age') to both collector_e and f
            }
        """
        if type(collect_dict) is not dict:
            raise AttributeError(f'{const.COLLECTOR_CONFIGURATION} is not dict')

        for _, collector in collect_dict.items():
            collectors = collector if isinstance(collector, (list, tuple)) else (collector,)
            for c in collectors:
                if c not in self.collect_set:
                    raise MissingCollector(f'Collector alias name not found in ancestor, please check: {kls_name}')

    def _populate_ancestors(self, parents: list) -> None:
        """
        mark should traverse to plan a minimal traversal path
        """
        for field, kls_name in parents:
            # normally, array size is small
            if field in self.metadata[kls_name]['raw_object_fields'] and \
                    field not in self.metadata[kls_name]['object_fields']:
                self.metadata[kls_name]['object_fields'].append(field)
            self.metadata[kls_name]['should_traverse'] = True

    def _should_skip_processing(self, kls_name: str, ancestors: list) -> bool:
        """Check if processing should be skipped (already cached and no traversal needed)."""
        cached_metadata = self.metadata.get(kls_name)
        if not cached_metadata:
            return False

        if cached_metadata['should_traverse'] or _has_config(cached_metadata):
            self._populate_ancestors(ancestors)
        return True

    def _prepare_class_context(self, kls: type, kls_name: str) -> FieldContext:
        """Prepare class context: configuration, field extraction, and validation."""
        # Based on ER diagram, generate resolve + dataloader by field's metadata settings
        if self.er_pre_generator:
            self.er_pre_generator.prepare(kls)

        # Generate expose and collector config based on field's metadata settings
        # __pydantic_resolve_expose__ and __pydantic_resolve_collect__
        pre_generate_expose_config(kls)
        pre_generate_collector_config(kls)

        # Prepare fields, with resolve_, post_ reserved
        all_fields, object_fields, object_field_pairs = _get_all_fields_and_object_fields(kls)
        resolve_fields, post_fields, fields_with_resolver = _get_resolve_and_post_fields(kls)
        _validate_resolve_and_post_fields(resolve_fields, post_fields, all_fields)
        object_fields_without_resolver = [a[0] for a in object_fields if a[0] not in fields_with_resolver]

        # Scan expose and collect (__pydantic_resolve_xxx__)
        expose_dict = getattr(kls, const.EXPOSE_TO_DESCENDANT, {})
        collect_dict = getattr(kls, const.COLLECTOR_CONFIGURATION, {})
        self._validate_expose(expose_dict, kls_name)

        return {
            'all_fields': all_fields,
            'object_fields': object_fields,
            'object_field_pairs': object_field_pairs,
            'resolve_fields': resolve_fields,
            'post_fields': post_fields,
            'fields_with_resolver': fields_with_resolver,
            'object_fields_without_resolver': object_fields_without_resolver,
            'expose_dict': expose_dict,
            'collect_dict': collect_dict,
        }

    def _scan_and_validate_methods(self, kls: type, ctx: FieldContext) -> MethodContext:
        """Scan method parameters and validate configuration."""
        resolve_fields = ctx['resolve_fields']
        post_fields = ctx['post_fields']
        object_field_pairs = ctx['object_field_pairs']
        collect_dict = ctx['collect_dict']
        kls_name = class_util.get_kls_full_name(kls)

        resolve_params = {
            field: _scan_resolve_method(
                getattr(kls, field),
                field,
                object_field_pairs.get(field.replace(const.RESOLVE_PREFIX, '')))
            for field in resolve_fields
        }
        post_params = {
            field: _scan_post_method(
                getattr(kls, field),
                field,
                object_field_pairs.get(field.replace(const.POST_PREFIX, '')))
            for field in post_fields
        }
        post_default_handler_params = _scan_post_default_handler(getattr(kls, const.POST_DEFAULT_HANDLER)) if _has_post_default_handler(kls) else None

        # Check context config
        resolve_context = any([p['context'] for p in resolve_params.values()])
        post_context = any([p['context'] for p in post_params.values()])
        post_default_context = post_default_handler_params['context'] if post_default_handler_params else False
        has_context = resolve_context or post_context or post_default_context

        # Check collector
        self._add_collector_info(post_params)
        self._add_collector_info_for_default_handler(post_default_handler_params)
        self._validate_collector(collect_dict, kls_name)

        return {
            'resolve_params': resolve_params,
            'post_params': post_params,
            'post_default_handler_params': post_default_handler_params,
            'has_context': has_context,
        }

    def _build_and_store_metadata(self, kls: type, kls_name: str, field_ctx: FieldContext, method_ctx: MethodContext) -> KlsMetaType:
        """Build and store metadata."""
        metadata: KlsMetaType = {
            'resolve': field_ctx['resolve_fields'],
            'resolve_params': method_ctx['resolve_params'],
            'post': field_ctx['post_fields'],
            'post_params': method_ctx['post_params'],
            'post_default_handler_params': method_ctx['post_default_handler_params'],
            'raw_object_fields': field_ctx['object_fields_without_resolver'],
            'object_fields': [],
            'expose_dict': field_ctx['expose_dict'],
            'collect_dict': field_ctx['collect_dict'],
            'kls': kls,
            'has_context': method_ctx['has_context'],
            'should_traverse': False
        }
        self.metadata[kls_name] = metadata
        return metadata

    def _traverse_child_objects(self, field_ctx: FieldContext, kls_name: str, ancestors: list) -> None:
        """Recursively traverse child objects."""
        object_fields = field_ctx['object_fields']
        object_fields_without_resolver = field_ctx['object_fields_without_resolver']
        fields_with_resolver = field_ctx['fields_with_resolver']

        # Visit fields (pydantic class) without resolve method
        for field, shelled_types in (obj for obj in object_fields if obj[0] in object_fields_without_resolver):
            for shelled_type in shelled_types:
                self._walker(shelled_type, ancestors + [(field, kls_name)])

        # Visit fields with resolve method
        for field, shelled_types in (obj for obj in object_fields if obj[0] in fields_with_resolver):
            for shelled_type in shelled_types:
                self._walker(shelled_type, ancestors + [(field, kls_name)])

    def _mark_for_traversal_if_needed(self, metadata: KlsMetaType, kls_name: str, ancestors: list) -> None:
        """Mark for traversal if needed."""
        should_traverse = metadata['should_traverse'] or _has_config(metadata)

        if should_traverse:
            self._populate_ancestors(ancestors)

        metadata['should_traverse'] = should_traverse

    def _walker(self, kls: type, ancestors: list[tuple[str, str]]) -> None:
        kls_name = class_util.get_kls_full_name(kls)

        if self._should_skip_processing(kls_name, ancestors):
            return

        # Prepare class context (configuration and field extraction)
        field_context = self._prepare_class_context(kls, kls_name)

        # Scan methods and validate
        method_context = self._scan_and_validate_methods(kls, field_context)

        # Build and store metadata
        metadata = self._build_and_store_metadata(kls, kls_name, field_context, method_context)

        # Traverse child objects
        self._traverse_child_objects(field_context, kls_name, ancestors)

        # Mark for traversal if needed
        self._mark_for_traversal_if_needed(metadata, kls_name, ancestors)

    def scan(self, root_class: type) -> MetaType:
        """Public method to perform metadata scan and return the metadata map."""
        # reset state for each scan
        self.expose_set = set()
        self.collect_set = set()
        self.metadata = {}

        core_types = class_util.get_core_types(root_class)

        for ct in core_types:
            class_util.update_forward_refs(ct)

        for ct in core_types:
            self._walker(ct, [])

        return self.metadata


def convert_metadata_key_as_kls(metadata: MetaType) -> MappedMetaType:  # type: ignore[valid-type]
    """ use kls as map key for performance """
    kls_metadata: MappedMetaType = {}
    for k, v in metadata.items():
        _kls_meta: MappedMetaMemberType = {
            **v, 
            'kls_path':k,
            'alias_map_proto': {}
        }
        alias_map = _calc_alias_map_from_collectors(_kls_meta)
        _kls_meta['alias_map_proto'] = alias_map
        kls_metadata[v['kls']] = _kls_meta
    
    return kls_metadata


def _calc_alias_map_from_collectors(kls_meta: MappedMetaMemberType) -> dict:
    post_params = kls_meta['post_params']
    kls_path = kls_meta['kls_path']

    alias_map = defaultdict(dict)

    def add_collector(collector: CollectorType) -> None:
        """
        class A(BaseModel):
            def post_name(collector_a=Collector('name_collector')):
                ...
        kls_path: module_name.A
        field: post_name
        param: collector_a

        sign = ('module_name.A', 'post_name', 'collector_a')

        return { 'name_collector': { sign: collector_instance } }
        """
        sign = get_collector_sign(kls_path, collector)
        alias_map[collector['alias']][sign] = collector['instance']

    for _, param in post_params.items():
        for collector in param['collectors']:
            add_collector(collector)

    # post_default_handler
    post_default_handler_params = kls_meta['post_default_handler_params']
    if post_default_handler_params:
        for collector in post_default_handler_params['collectors']:
            add_collector(collector)

    return alias_map


def is_acceptable_kls(kls: type) -> bool:
    return class_util.safe_issubclass(kls, BaseModel)


def is_acceptable_instance(target: object):
    return isinstance(target, BaseModel)


def get_resolve_fields_and_object_fields_from_object(node: object, kls: type, mapped_metadata: MappedMetaType):
    """
    resolve_fields: a field with resolve_field method
    object_fields: a field without resolve_field method but is an object (should traversal)
    """
    resolve_fields, object_fields = [], []
    kls_meta = mapped_metadata.get(kls)

    if kls_meta is None:
        return [], []

    for resolve_field in kls_meta['resolve']:
        attr = getattr(node, resolve_field)
        trim_field = kls_meta['resolve_params'][resolve_field]['trim_field']
        resolve_fields.append((resolve_field, trim_field, attr))

    for attr_name in kls_meta['object_fields']:
        attr = getattr(node, attr_name)
        object_fields.append((attr_name, attr))

    return resolve_fields, object_fields


def get_post_methods(node: object, kls: type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls)

    if kls_meta is None:
        return []

    for post_field in kls_meta['post']:
        attr = getattr(node, post_field)
        trim_field = kls_meta['post_params'][post_field]['trim_field']
        yield post_field, trim_field, attr


def get_resolve_method_param(kls: type, resolve_field: str, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['resolve_params'][resolve_field]


def get_post_method_params(kls: type, post_field: str, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['post_params'][post_field]


def get_post_default_handler_params(kls: type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return kls_meta['post_default_handler_params']


def get_collector_sign(kls_path: str, collector: CollectorType) -> tuple:
    return (kls_path, collector['field'], collector['param'])


def generate_alias_map_with_cloned_collector(kls: type, mapped_metadata: MappedMetaType):
    kls_meta = mapped_metadata.get(kls, {})
    return { alias: {
        sign: copy.deepcopy(collector) for sign, collector in v.items()
    } for alias, v in kls_meta['alias_map_proto'].items()}


def get_collector_candidates(kls: type, metadata: MappedMetaType):
    kls_meta = metadata.get(kls, {})
    collect_dict = kls_meta['collect_dict']

    for field, alias in collect_dict.items():
        yield field, alias


def has_context(mapped_metadata: MappedMetaType):
    return any([ m['has_context'] for m in mapped_metadata.values()])