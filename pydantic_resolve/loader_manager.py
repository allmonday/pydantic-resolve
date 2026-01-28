from inspect import isclass

import pydantic_resolve.utils.class_util as class_util
import pydantic_resolve.utils.params as params_util
from pydantic_resolve.analysis import LoaderQueryMeta, MappedMetaType
from pydantic_resolve.exceptions import LoaderFieldNotProvidedError

from aiodataloader import DataLoader
from pydantic import BaseModel


class LoaderManager:
    """
    Refactor loader instance validation/creation into a class.

    Public API:
      - validate_and_create_loader_instance(self, loader_params, global_loader_param, loader_instances, metadata)
    """

    def __init__(self) -> None:
        pass

    # fetch all loaders
    def _get_all_loaders_from_meta(self, metadata: MappedMetaType):
        for _, kls_info in metadata.items():
            for _, resolve_info in kls_info['resolve_params'].items():
                for loader in resolve_info['dataloaders']:
                    yield loader

            for _, post_info in kls_info['post_params'].items():
                for loader in post_info['dataloaders']:
                    yield loader

    def _create_instance(self, loader, loader_params, global_loader_param, loader_instances):
        """
        1. is class?
            - validate params
        2. is func
        """
        loader_kls, path = loader['kls'], loader['path']
        if isclass(loader_kls):
            loader_instance = loader_kls()
            param_config = params_util.merge_dicts(
                global_loader_param,
                loader_params.get(loader_kls, {}))

            for field, has_default in class_util.get_fields_default_value_not_provided(loader_kls):
                try:
                    if has_default and field not in param_config:
                        continue

                    value = param_config[field]
                    setattr(loader_instance, field, value)
                except KeyError:
                    raise LoaderFieldNotProvidedError(f'{path}.{field} not found in Resolver()')
            return loader_instance
        else:
            return DataLoader(batch_load_fn=loader_kls)  # type:ignore

    def _get_all_fields(self, kls: type):
        if class_util.safe_issubclass(kls, BaseModel):
            return list(class_util.get_pydantic_field_keys(kls))
        else:
            raise AttributeError('invalid type: should be pydantic object')  # noqa

    def _generate_meta(self, types: list[list[type]]):
        _fields = set()
        meta: LoaderQueryMeta = {
            'fields': [],
            'request_types': []
        }

        for tt in types:
            for t in tt:
                fields = self._get_all_fields(t)
                meta['request_types'].append(dict(name=t, fields=fields))
                _fields.update(fields)
        meta['fields'] = list(_fields)
        return meta

    def validate_and_create_loader_instance(
        self,
        loader_params,
        global_loader_param,
        loader_instances,
        metadata: MappedMetaType
    ):
        """
        return loader_instance_cache

        validate: whether loader params are missing
        create:
            - func
            - loader class
                - no param
                - has param
        """
        cache = {}
        request_info = {}

        # create instance
        for loader in self._get_all_loaders_from_meta(metadata):
            loader_kls, path = loader['kls'], loader['path']

            if path in cache:
                continue

            if loader_instances.get(loader_kls):  # if instance already exists
                cache[path] = loader_instances.get(loader_kls)
                continue

            cache[path] = self._create_instance(loader, loader_params, global_loader_param, loader_instances)

        # prepare query meta
        for loader in self._get_all_loaders_from_meta(metadata):
            kls, path = loader['request_type'], loader['path']

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
            instance._query_meta = self._generate_meta(request_info[path])

        return cache


def validate_and_create_loader_instance(
        loader_params,
        global_loader_param,
        loader_instances,
        metadata: MappedMetaType):

    return LoaderManager().validate_and_create_loader_instance(
        loader_params=loader_params,
        global_loader_param=global_loader_param,
        loader_instances=loader_instances,
        metadata=metadata,
    )