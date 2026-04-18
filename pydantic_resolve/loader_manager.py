from inspect import isclass
from typing import Any, Generator

import pydantic_resolve.utils.class_util as class_util
import pydantic_resolve.utils.params as params_util
from pydantic_resolve.analysis import LoaderQueryMeta, MappedMetaType
from pydantic_resolve.exceptions import LoaderFieldNotProvidedError, LoaderContextNotProvidedError

from aiodataloader import DataLoader
from pydantic import BaseModel


# Type definitions
LoaderType = dict[str, Any]


def _validate_loader_context_requirements(
    metadata: MappedMetaType,
    has_resolver_context: bool
) -> None:
    """Validate that all DataLoaders requiring context will receive it.

    Args:
        metadata: The scanned metadata
        has_resolver_context: Whether Resolver has context provided

    Raises:
        LoaderContextNotProvidedError: If a loader needs context but none is provided
    """
    loaders_needing_context = []

    for loader in _get_all_loaders_from_meta(metadata):
        if loader.get('requires_context', False) and not has_resolver_context:
            loader_kls = loader['kls']
            path = loader['path']
            loaders_needing_context.append((path, loader_kls.__name__))

    if loaders_needing_context:
        paths = ', '.join([f"{name} ({path})" for path, name in loaders_needing_context])
        raise LoaderContextNotProvidedError(
            f"DataLoader(s) require context but Resolver doesn't provide one: {paths}. "
            f"Please provide context to Resolver, e.g., Resolver(context={{'user_id': 123}})"
        )



def _get_all_loaders_from_meta(metadata: MappedMetaType) -> Generator[LoaderType, None, None]:
    """Fetch all loaders from metadata."""
    for _, kls_info in metadata.items():
        for _, resolve_info in kls_info['resolve_params'].items():
            for loader in resolve_info['dataloaders']:
                yield loader

        for _, post_info in kls_info['post_params'].items():
            for loader in post_info['dataloaders']:
                yield loader


def _create_loader_instance(
    loader: LoaderType,
    loader_params: dict,
    global_loader_param: dict,
    context: dict | None = None
) -> DataLoader:
    """
    Create a loader instance.

    1. is class?
        - validate params
        - set context if required
    2. is func
    """
    loader_kls = loader['kls']
    path = loader['path']

    if isclass(loader_kls):
        loader_instance = loader_kls()
        param_config = params_util.merge_dicts(
            global_loader_param,
            loader_params.get(loader_kls, {}))

        for field, has_default in class_util.get_fields_default_value_not_provided(loader_kls):
            # Skip _context field - it will be set separately
            if field == '_context':
                continue

            try:
                if has_default and field not in param_config:
                    continue

                value = param_config[field]
                setattr(loader_instance, field, value)
            except KeyError:
                raise LoaderFieldNotProvidedError(f'{path}.{field} not found in Resolver()')

        # Set _context if loader requires it and context is provided
        if loader.get('requires_context', False) and context is not None:
            setattr(loader_instance, '_context', context)

        return loader_instance
    else:
        return DataLoader(batch_load_fn=loader_kls)  # type:ignore


def _get_all_fields(kls: type) -> list[str]:
    """Get all field keys from a Pydantic model."""
    if class_util.safe_issubclass(kls, BaseModel):
        return list(class_util.get_pydantic_field_keys(kls))
    else:
        raise AttributeError('invalid type: should be pydantic object')  # noqa


def _generate_query_meta(types: list[list[type]]) -> LoaderQueryMeta:
    """Generate query metadata from request types."""
    _fields = set()
    meta: LoaderQueryMeta = {
        'fields': [],
        'request_types': []
    }

    for tt in types:
        for t in tt:
            fields = _get_all_fields(t)
            meta['request_types'].append(dict(name=t, fields=fields))
            _fields.update(fields)
    meta['fields'] = list(_fields)
    return meta


def validate_and_create_loader_instance(
    loader_params: dict,
    global_loader_param: dict,
    loader_instances: dict,
    metadata: MappedMetaType,
    context: dict | None = None,
    split_loader_by_type: bool = False
) -> dict[str, DataLoader] | dict[str, dict[tuple[type, ...], DataLoader]]:
    """
    Validate and create loader instances.

    validate: whether loader params are missing, and whether context is required but not provided
    create:
        - func
        - loader class
            - no param
            - has param

    Returns:
        Default mode (split_loader_by_type=False):
            dict[str, DataLoader] — flat mapping from loader path to instance.
        Split mode (split_loader_by_type=True):
            dict[str, dict[tuple[type, ...], DataLoader]] — nested mapping.
            Outer key is loader path, inner key is sorted tuple of request_types.

    Data transformation example (split mode):

        Given: Dashboard.resolve_cards  (request_type=[TaskCard])
               Dashboard.resolve_details (request_type=[TaskDetail])

        Phase 1 → cache:
          {'mod.TaskLoader': {
            (TaskCard,): <TaskLoader inst1>,
            (TaskDetail,): <TaskLoader inst2>,
          }}

        Phase 2 → type_keys:
          {'mod.TaskLoader': {(TaskCard,), (TaskDetail,)}}
          Each type_key is a sorted tuple. If a field annotation were `TaskA | TaskB`,
          the type_key would be (TaskA, TaskB) (sorted by full class name to normalize Union order).

        Phase 3 → _query_meta:
          _generate_query_meta expands each type_key into its Pydantic fields:
            inst1._query_meta = {
              'fields': ['id', 'title'],
              'request_types': [{'name': TaskCard, 'fields': ['id', 'title']}]
            }

    Data transformation example (default / non-split mode):

        Same scenario: Dashboard.resolve_cards + Dashboard.resolve_details

        Phase 1 → cache (key is always ()):
          {'mod.TaskLoader': {(): <TaskLoader shared_inst>}}

        Phase 2 → type_keys (same as split, just collecting unique type_keys):
          {'mod.TaskLoader': {(TaskCard,), (TaskDetail,)}}

        Phase 3 → _query_meta (all type_keys feed into one shared instance):
          shared_inst._query_meta = {
            'fields': ['id', 'title', 'desc', 'status', ...],  # union across all types
            'request_types': [
              {'name': TaskCard, 'fields': ['id', 'title']},
              {'name': TaskDetail, 'fields': ['id', 'title', 'desc', 'status', ...]},
            ]
          }

        Return → flattened to {'mod.TaskLoader': <shared_inst>}
    """
    # Validate context requirements first
    _validate_loader_context_requirements(metadata, context is not None)

    # split_loader_by_type is incompatible with pre-created loader_instances
    # because split requires creating separate DataLoader instances per request_type,
    # but loader_instances provides a single shared instance per loader class.
    if split_loader_by_type and loader_instances:
        raise ValueError(
            'split_loader_by_type=True is incompatible with loader_instances. '
            'When splitting loaders by type, each split requires an independent '
            'DataLoader instance, which conflicts with pre-created shared instances.'
        )

    # Internally always use nested structure {path: {key: DataLoader}}:
    #   split mode:  key = type_key  (one instance per request_type set)
    #   default mode: key = ()       (all entries share the same key → one instance per path)
    cache: dict[str, dict[tuple[type, ...], DataLoader]] = {}
    # type_keys collects unique type_key sets per loader path.
    # type_key is a sorted tuple of request types (e.g. (TaskCard,) or (TaskA, TaskB)),
    # used both as cache key in split mode and as type source for _query_meta generation.
    type_keys: dict[str, set[tuple[type, ...]]] = {}

    # Phase 1: create instances
    # Iterate all DataLoaderType entries from scanned metadata (resolve_* and post_* methods).
    # - Non-split mode: key = (), so every path maps to exactly one instance.
    # - Split mode:     key = type_key (sorted tuple of request types), creating one instance per type set.
    #
    # Result (non-split):  cache = {'mod.TaskLoader': {(): <TaskLoader inst>}}
    # Result (split):      cache = {'mod.TaskLoader': {(TaskCard,): <inst1>, (TaskDetail,): <inst2>}}
    for loader in _get_all_loaders_from_meta(metadata):
        path = loader['path']
        key = () if not split_loader_by_type else loader['type_key']

        if path not in cache:
            cache[path] = {}
        if key in cache[path]:
            continue

        loader_kls = loader['kls']
        if loader_instances.get(loader_kls):
            cache[path][key] = loader_instances[loader_kls]
        else:
            cache[path][key] = _create_loader_instance(loader, loader_params, global_loader_param, context)

    # Phase 2: collect type_keys for _query_meta generation.
    # A set naturally deduplicates — Union alternatives with different order
    # (e.g. TaskA|TaskB vs TaskB|TaskA) produce the same sorted type_key.
    #
    # Result: type_keys = {'mod.TaskLoader': {(TaskCard,), (TaskDetail,)}}
    for loader in _get_all_loaders_from_meta(metadata):
        if loader['request_type'] is None:
            continue
        type_keys.setdefault(loader['path'], set()).add(loader['type_key'])

    # Phase 3: assign _query_meta
    # For each instance, determine which type_keys are relevant:
    #   - Non-split: all type_keys (shared instance serves all types)
    #   - Split:     only the type_key matching this instance's key
    # _generate_query_meta expands each type into its Pydantic fields:
    #   - fields:         union of all columns (for SQL column pruning)
    #   - request_types:  per-type field lists (for type-specific queries)
    for path, inner in cache.items():
        keys = type_keys.get(path)
        if not keys:  # do nothing, leave it to `not split_loader_by_type`
            continue
        for key, instance in inner.items():
            relevant = keys if not split_loader_by_type else keys & {key}
            if relevant:
                # Sort to ensure deterministic _query_meta output order
                sorted_keys = sorted(relevant, key=lambda tk: tuple(class_util.get_kls_full_name(t) for t in tk))
                instance._query_meta = _generate_query_meta([list(tk) for tk in sorted_keys])

    # Flatten for non-split mode: extract the sole () entry from each path's inner dict
    # to produce the flat {path: DataLoader} return type.
    if not split_loader_by_type:
        return {path: inner[()] for path, inner in cache.items()}
    return cache
