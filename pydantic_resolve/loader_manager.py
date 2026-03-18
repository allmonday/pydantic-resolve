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
    context: dict | None = None
) -> dict[str, DataLoader]:
    """
    Validate and create loader instances.

    validate: whether loader params are missing, and whether context is required but not provided
    create:
        - func
        - loader class
            - no param
            - has param
    """
    # Validate context requirements first
    _validate_loader_context_requirements(metadata, context is not None)

    cache: dict[str, DataLoader] = {}
    request_info: dict[str, list[type]] = {}

    # create instance
    for loader in _get_all_loaders_from_meta(metadata):
        loader_kls = loader['kls']
        path = loader['path']

        if path in cache:
            continue

        if loader_instances.get(loader_kls):  # if instance already exists
            cache[path] = loader_instances.get(loader_kls)
            continue

        cache[path] = _create_loader_instance(loader, loader_params, global_loader_param, context)

    # prepare query meta
    for loader in _get_all_loaders_from_meta(metadata):
        kls = loader['request_type']
        path = loader['path']

        if kls is None:
            continue

        if path in request_info and kls not in request_info[path]:
            request_info[path].append(kls)
        else:
            request_info[path] = [kls]

    # combine together
    for path, instance in cache.items():
        if request_info.get(path) is None:
            continue
        instance._query_meta = _generate_query_meta(request_info[path])

    return cache
