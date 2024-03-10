import asyncio
import types
import functools
from collections import defaultdict
from dataclasses import is_dataclass
from pydantic import BaseModel, parse_obj_as, ValidationError
from inspect import iscoroutine, isfunction
from typing import Any, DefaultDict, Sequence, Type, TypeVar, List, Callable, Optional, Mapping, Union, Iterator, Dict, get_type_hints
import pydantic_resolve.constant as const
from pydantic_resolve.exceptions import GlobalLoaderFieldOverlappedError
from aiodataloader import DataLoader

def get_class_field_annotations(cls: Type):
    anno = cls.__dict__.get('__annotations__') or {}
    return anno.keys()


T = TypeVar("T")
V = TypeVar("V")

def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]):
    overlap = set(a.keys()) & set(b.keys())
    if overlap:
        raise GlobalLoaderFieldOverlappedError(f'loader_params and global_loader_param have duplicated key(s): {",".join(overlap)}')
    else:
        return {**a, **b}

def build_object(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> Iterator[Optional[T]]:
    """
    helper function to build return object data required by aiodataloader
    """
    dct: Mapping[V, T] = {}
    for item in items:
        _key = get_pk(item)
        dct[_key] = item
    results = (dct.get(k, None) for k in keys)
    return results

def build_list(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> Iterator[List[T]]:
    """
    helper function to build return list data required by aiodataloader
    """
    dct: DefaultDict[V, List[T]] = defaultdict(list) 
    for item in items:
        _key = get_pk(item)
        dct[_key].append(item)
    results = (dct.get(k, []) for k in keys)
    return results

def replace_method(cls: Type, cls_name: str, func_name: str, func: Callable):
    """test-only"""
    KLS = type(cls_name, (cls,), {func_name: func})
    return KLS


def get_required_fields(kls: BaseModel):
    required_fields = []

    # 1. get required fields
    for fname, field in kls.__fields__.items():
        if field.required:
            required_fields.append(fname)

    # 2. get resolve_ and post_ target fields
    for f in dir(kls):
        if f.startswith(const.PREFIX):
            if isfunction(getattr(kls, f)):
                required_fields.append(f.replace(const.PREFIX, ''))

        if f.startswith(const.POST_PREFIX):
            if isfunction(getattr(kls, f)):
                required_fields.append(f.replace(const.POST_PREFIX, ''))

    return required_fields

def output(kls):
    """
    set required as True for all fields, make typescript code gen result friendly to use
    """
    if issubclass(kls, BaseModel):
        def _schema_extra(schema: Dict[str, Any], model) -> None:
            fnames = get_required_fields(model)
            schema['required'] = fnames

        kls.__config__.schema_extra = staticmethod(_schema_extra)

    else:
        raise AttributeError(f'target class {kls.__name__} is not BaseModel')
    return kls

def model_config(hidden_fields: Optional[List[str]]=None, default_required: bool = True):
    """
    - hidden_fields: fields want to hide
    - default_required: 
        if resolve field has default value, it will not be listed in schema['required']
        set default_required=True to add it into required list.
    """
    def wrapper(kls):
        if issubclass(kls, BaseModel):
            # handle __exclude_fields__ 
            if hidden_fields:
                # validate
                for f in hidden_fields:
                    if f not in kls.__fields__.keys():
                        raise KeyError(f'{f} is not valid')

                # exclude in dict()
                excludes_fields = kls.__exclude_fields__ or {}
                hiddens_fields = {k: True for k in hidden_fields}
                kls.__exclude_fields__ = {**excludes_fields, **hiddens_fields}
                
            # override schema_extra method
            def _schema_extra(schema: Dict[str, Any], model) -> None:
                # define schema.properties
                excludes = set()

                if hidden_fields:
                    for hf in hidden_fields:
                        excludes.add(hf)

                if kls.__exclude_fields__:
                    for k in kls.__exclude_fields__.keys():
                        excludes.add(k)

                props = {}
                for k, v in schema.get('properties', {}).items():
                    if k not in excludes:
                        props[k] = v
                schema['properties'] = props

                # define schema.required
                if default_required:
                    fnames = get_required_fields(model)
                    if hidden_fields:
                        fnames = [n for n in fnames if n not in hidden_fields]
                    schema['required'] = fnames
            kls.__config__.schema_extra = staticmethod(_schema_extra)
        else:
            raise AttributeError(f'target class {kls.__name__} is not BaseModel')
        return kls
    return wrapper

def mapper(func_or_class: Union[Callable, Type]):
    """
    execute post-transform function after the value is reolved
    func_or_class:
        is func: run func
        is class: call auto_mapping to have a try
    """
    def inner(inner_fn):

        # if mapper provided, auto map from target type will be disabled
        setattr(inner_fn, const.HAS_MAPPER_FUNCTION, True)

        @functools.wraps(inner_fn)
        async def wrap(*args, **kwargs):

            retVal = inner_fn(*args, **kwargs)
            while iscoroutine(retVal) or asyncio.isfuture(retVal):
                retVal = await retVal  # get final result
            
            if retVal is None:
                return None

            if isinstance(func_or_class, types.FunctionType):
                # manual mapping
                return func_or_class(retVal)
            else:
                # auto mapping
                if isinstance(retVal, list):
                    if retVal:
                        rule = _get_mapping_rule(func_or_class, retVal[0])
                        return _apply_rule(rule, func_or_class, retVal, True)
                    else:
                        return retVal  # return []
                else:
                    rule = _get_mapping_rule(func_or_class, retVal)
                    return _apply_rule(rule, func_or_class, retVal, False)
        return wrap
    return inner

def _get_mapping_rule(target, source) -> Optional[Callable]:
    # do noting
    if isinstance(source, target):
        return None

    # pydantic
    if issubclass(target, BaseModel):
        if target.__config__.orm_mode:
            if isinstance(source, dict):
                raise AttributeError(f"{type(source)} -> {target.__name__}: pydantic from_orm can't handle dict object")
            else:
                return lambda t, s: t.from_orm(s)

        if isinstance(source, (dict, BaseModel)):
            return lambda t, s: t.parse_obj(s)

        else:
            raise AttributeError(f"{type(source)} -> {target.__name__}: pydantic can't handle non-dict data")

    # dataclass
    if is_dataclass(target):
        if isinstance(source, dict):
            return lambda t, s: t(**s)

    raise NotImplementedError(f"{type(source)} -> {target.__name__}: faild to get auto mapping rule and execut mapping, use your own rule instead.")

def _apply_rule(rule: Optional[Callable], target, source: Any, is_list: bool):
    if not rule:  # no change
        return source

    if is_list:
        return [rule(target, s) for s in source]
    else:
        return rule(target, source)

def ensure_subset(base):
    """
    used with pydantic class to make sure a class's field is 
    subset of target class
    """
    def wrap(kls):
        assert issubclass(base, BaseModel), 'base should be pydantic class'
        assert issubclass(kls, BaseModel), 'class should be pydantic class'

        @functools.wraps(kls)
        def inner():
            for k, field in kls.__fields__.items():
                if field.required:
                    base_field = base.__fields__.get(k)
                    if not base_field:
                        raise AttributeError(f'{k} not existed in {base.__name__}.')
                    if base_field and base_field.type_ != field.type_:
                        raise AttributeError(f'type of {k} not consistent with {base.__name__}'  )
            return kls
        return inner()
    return wrap

def update_forward_refs(kls):
    def update_pydantic_forward_refs(kls: Type[BaseModel]):
        """
        recursively update refs.
        """
        if getattr(kls, const.PYDANTIC_FORWARD_REF_UPDATED, False):
            return
        kls.update_forward_refs()
        setattr(kls, const.PYDANTIC_FORWARD_REF_UPDATED, True)

        for field in kls.__fields__.values():
            shelled_type = shelling_type(field.type_)
            update_forward_refs(shelled_type)

    def update_dataclass_forward_refs(kls):
        if not getattr(kls, const.DATACLASS_FORWARD_REF_UPDATED, False):
            anno = get_type_hints(kls)
            kls.__annotations__ = anno
            setattr(kls, const.DATACLASS_FORWARD_REF_UPDATED, True)

            for _, v in kls.__annotations__.items():
                shelled_type = shelling_type(v)
                update_forward_refs(shelled_type)

    if issubclass(kls, BaseModel):
        update_pydantic_forward_refs(kls)

    if is_dataclass(kls):
        update_dataclass_forward_refs(kls)

def try_parse_data_to_target_field_type(target, field_name, data):
    """
    parse to pydantic or dataclass object
    1. get type of target field
    2. parse
    """
    field_type = None

    # 1. get type of target field
    if isinstance(target, BaseModel):
        _fields = target.__class__.__fields__
        field_type = _fields[field_name].outer_type_

        # handle optional logic
        if data is None and _fields[field_name].required == False:
            return data

    elif is_dataclass(target):
        field_type = target.__class__.__annotations__[field_name]

    # 2. parse
    if field_type:
        try:
            result = parse_obj_as(field_type, data)
            return result
        except ValidationError as e:
            print(f'Warning: type mismatch, pls check the return type for "{field_name}", expected: {field_type}')
            raise e
    else:
        return data  #noqa

def _is_optional(annotation):
    annotation_origin = getattr(annotation, "__origin__", None)
    return annotation_origin == Union \
        and len(annotation.__args__) == 2 \
        and annotation.__args__[1] == type(None)  # noqa

def _is_list(annotation):
    return getattr(annotation, "__origin__", None) == list

def shelling_type(type):
    while _is_optional(type) or _is_list(type):
        type = type.__args__[0]
    return type

def get_kls_full_path(kls):
    return f'{kls.__module__}.{kls.__qualname__}'

def copy_dataloader_kls(name, loader_kls):
    """
    quickly copy from an existed DataLoader class
    usage:
    SeniorMemberLoader = copy_dataloader('SeniorMemberLoader', ul.UserByLevelLoader)
    JuniorMemberLoader = copy_dataloader('JuniorMemberLoader', ul.UserByLevelLoader)
    """
    return type(name, loader_kls.__bases__, dict(loader_kls.__dict__))

class StrictEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        """it should not be triggered, otherwise will raise Exception"""
        raise ValueError('EmptyLoader should load from pre loaded data')

class ListEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        dct = {}
        return [dct.get(k, []) for k in keys]

class SingleEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        dct = {}
        return [dct.get(k, None) for k in keys]

def generate_strict_empty_loader(name):
    """generated Loader will raise ValueError if not found"""
    return type(name, StrictEmptyLoader.__bases__, dict(StrictEmptyLoader.__dict__))  #noqa

def generate_list_empty_loader(name):
    """generated Loader will return [] if not found"""
    return type(name, ListEmptyLoader.__bases__, dict(ListEmptyLoader.__dict__))  #noqa

def generate_single_empty_loader(name):
    """generated Loader will return None if not found"""
    return type(name, SingleEmptyLoader.__bases__, dict(SingleEmptyLoader.__dict__))  #noqa