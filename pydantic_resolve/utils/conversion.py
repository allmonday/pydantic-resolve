import asyncio
import functools
import types
from inspect import iscoroutine
from typing import Any, Callable, Optional, Type, Union
from pydantic import BaseModel, ValidationError, TypeAdapter
import pydantic_resolve.constant as const
from pydantic_resolve.utils.class_util import safe_issubclass

class TypeAdapterManager:
    apapters = {}
    
    @classmethod
    def get(cls, type):
        adapter = cls.apapters.get(type)
        if adapter:
            return adapter
        else:
            new_adapter = TypeAdapter(type)
            cls.apapters[type] = new_adapter
            return new_adapter


def try_parse_data_to_target_field_type(
        target: object,
        field_name: str,
        data,
        enable_from_attribute=False):
    """
    parse input to pydantic object
    1. get type of target field
    2. parse
    """
    field_type = None

    # from_attribute by default is None
    # if set False it will fail when dealing with namedtuple
    _enable_from_attribute = True if enable_from_attribute else None 

    # 1. get type of target field
    if isinstance(target, BaseModel):
        _fields = target.__class__.model_fields
        field_type = _fields[field_name].annotation

        # handle optional logic
        if data is None and not _fields[field_name].is_required():
            return data

    # 2. parse
    if field_type:
        try:
            # https://docs.pydantic.dev/latest/concepts/performance/#typeadapter-instantiated-once
            adapter = TypeAdapterManager.get(field_type)
            result = adapter.validate_python(data, from_attributes=_enable_from_attribute)
            return result
        except ValidationError as e:
            print(f'Warning: type mismatch, pls check the return type for "{field_name}", expected: {field_type}')
            raise e

    else:
        return data  #noqa


def _get_mapping_rule(target, source) -> Optional[Callable]:
    # do noting
    if isinstance(source, target):
        return None

    # pydantic
    if safe_issubclass(target, BaseModel):
        if target.model_config.get('from_attributes'):
            if isinstance(source, dict):
                raise AttributeError(f"{type(source)} -> {target.__name__}: pydantic from_orm can't handle dict object")
            else:
                return lambda t, s: t.model_validate(s)

        if isinstance(source, dict):
            return lambda t, s: t.model_validate(s)

        if isinstance(source, BaseModel):
            if source.model_config.get('from_attributes'):
                return lambda t, s: t.model_validate(s)
            else:
                return lambda t, s: t(**s.model_dump())

        else:
            raise AttributeError(f"{type(source)} -> {target.__name__}: pydantic can't handle non-dict data")

    raise NotImplementedError(f"{type(source)} -> {target.__name__}: faild to get auto mapping rule and execut mapping, use your own rule instead.")


def _apply_rule(rule: Optional[Callable], target, source: Any, is_list: bool):
    if not rule:  # no change
        return source

    if is_list:
        return [rule(target, s) for s in source]
    else:
        return rule(target, source)


def mapper(func_or_class: Union[Callable, Type]):
    """
    execute post-transform function after the value is reolved
    func_or_class:
        is func: run func
        is class: call auto_mapping to have a try

    class K(BaseModel):
        id: int

        field: str = ''
        @mapper(lambda x: x.name)
        def resolve_field(self, loader=Loader(field_batch_load_fn)):
            return loader.load(self.id)
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