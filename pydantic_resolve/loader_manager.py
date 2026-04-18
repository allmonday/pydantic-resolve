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

    if not split_loader_by_type:
        # Default: flat structure {path: DataLoader}
        cache: dict[str, DataLoader] = {}
        request_info: dict[str, list[list[type]]] = {}
        seen_type_keys: dict[str, set] = {}

        # create instance
        for loader in _get_all_loaders_from_meta(metadata):
            path = loader['path']
            if path in cache:
                continue
            loader_kls = loader['kls']
            if loader_instances.get(loader_kls):
                cache[path] = loader_instances[loader_kls]
            else:
                cache[path] = _create_loader_instance(loader, loader_params, global_loader_param, context)

        # prepare query meta
        for loader in _get_all_loaders_from_meta(metadata):
            kls = loader['request_type']
            if kls is None:
                continue
            path = loader['path']
            type_key = loader['type_key']
            if path not in request_info:
                request_info[path] = []
                seen_type_keys[path] = set()
            # Dedup by type_key (sorted tuple) so Union order doesn't matter
            if type_key not in seen_type_keys[path]:
                request_info[path].append(kls)
                seen_type_keys[path].add(type_key)

        # combine
        for path, instance in cache.items():
            if request_info.get(path) is None:
                continue
            instance._query_meta = _generate_query_meta(request_info[path])

        return cache

    else:
        # Split: nested structure {path: {type_tuple: DataLoader}}
        cache: dict[str, dict[tuple[type, ...], DataLoader]] = {}  # type: ignore[no-redef]
        request_info: dict[str, dict[tuple[type, ...], list[list[type]]]] = {}  # type: ignore[no-redef]

        # create instance
        for loader in _get_all_loaders_from_meta(metadata):
            path = loader['path']
            type_key = loader['type_key']

            if path not in cache:
                cache[path] = {}
            if type_key in cache[path]:
                continue

            loader_kls = loader['kls']
            if loader_instances.get(loader_kls):
                cache[path][type_key] = loader_instances[loader_kls]
            else:
                cache[path][type_key] = _create_loader_instance(loader, loader_params, global_loader_param, context)

        # prepare query meta
        for loader in _get_all_loaders_from_meta(metadata):
            request_types = loader['request_type']
            if request_types is None:
                continue
            path = loader['path']
            type_key = loader['type_key']

            if path not in request_info:
                request_info[path] = {}
            # Same type_key means same type set (regardless of Union order);
            # keep only one representative request_types per type_key.
            if type_key not in request_info[path]:
                request_info[path][type_key] = [request_types]

        # combine
        for path, inner in cache.items():
            for type_key, instance in inner.items():
                if path in request_info and type_key in request_info[path]:
                    instance._query_meta = _generate_query_meta(request_info[path][type_key])

        return cache
