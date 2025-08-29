"""Experimental subset model creator.

目标: 让 Subset 和 A 除了字段集合被收窄以外保持一致 (字段类型/默认值/配置), 
而不是简单继承后再忽略字段 (那样无法真正移除父类字段)。

实现思路:
1. 传入 parent(BaseModel) 与想保留的 fields 列表。
2. 读取 parent 中对应字段的注解与默认值 (required / optional)。
3. 动态创建一个新的 BaseModel 子类 (不直接继承 parent, 以便真正只保留指定字段)。
4. 复制 parent 的 model_config (pydantic v2) / Config (pydantic v1) 与校验器(简单策略: 复制同名的 @validator/@field_validator 方法)。
5. 生成的新类即 Subset。 

注意: 这里只做最小演示, 校验器的复制只做浅层(名称以 "validate_" 前缀的函数)。
"""

import types
from typing import Callable, Type, Dict, Any, List
from pydantic import BaseModel
from pydantic_resolve.compat import PYDANTIC_V2


def replace_method(cls: Type, cls_name: str, func_name: str, func: Callable):  # noqa: D401
    """test-only helper: 返回一个替换单个方法后的类型"""
    KLS = type(cls_name, (cls,), {func_name: func})
    return KLS



def _extract_field_defs_from_parent(parent: Type[BaseModel], field_names: List[str]):
    annotations: Dict[str, Any] = {}
    defaults: Dict[str, Any] = {}

    if PYDANTIC_V2:
        for fname in field_names:
            fld = parent.model_fields.get(fname)
            if not fld:
                raise AttributeError(f'field "{fname}" not existed in {parent.__name__}')
            annotations[fname] = fld.annotation
            if not fld.is_required():  # 有默认值
                defaults[fname] = fld.default
    else:  # v1
        for fname in field_names:
            fld = parent.__fields__.get(fname)
            if not fld:
                raise AttributeError(f'field "{fname}" not existed in {parent.__name__}')
            annotations[fname] = fld.type_ if fld.outer_type_ is None else fld.outer_type_
            if not fld.required:
                defaults[fname] = fld.default

    return annotations, defaults


def _copy_parent_config(parent: Type[BaseModel]) -> Dict[str, Any]:
    if PYDANTIC_V2:
        return {'model_config': getattr(parent, 'model_config', None)}
    else:
        Config = getattr(parent, 'Config', None)
        return {'Config': Config} if Config else {}


def _copy_parent_validators(parent: Type[BaseModel]) -> Dict[str, Any]:
    copied = {}
    for attr_name, value in parent.__dict__.items():
        if callable(value) and attr_name.startswith('validate_'):
            copied[attr_name] = value
    return copied


BaseModelMeta = type(BaseModel)


class A(BaseModel):
    id: int
    name: str
    age: int

class MakeSubset(BaseModelMeta):
    def __new__(mcls, name, bases, attrs, parent: Type[BaseModel], fields: List[str]):
        if not issubclass(parent, BaseModel):
            raise TypeError('parent 必须是 pydantic BaseModel')

        # 若用户没显式继承 BaseModel, 自动补上
        if not bases:
            bases = (BaseModel,)
        elif BaseModel not in bases:
            bases = bases + (BaseModel,)

        uniq_fields = list(dict.fromkeys(fields))
        annotations, defaults = _extract_field_defs_from_parent(parent, uniq_fields)

        namespace: Dict[str, Any] = {
            '__module__': attrs.get('__module__', parent.__module__),
            '__annotations__': annotations,
            '__doc__': attrs.get('__doc__') or f'Subset of {parent.__name__}: {uniq_fields}',
        }
        namespace.update(defaults)
        namespace.update(_copy_parent_config(parent))
        namespace.update(_copy_parent_validators(parent))
        for k, v in attrs.items():
            if k.startswith('__') and k.endswith('__'):
                continue
            if k == '__annotations__':
                continue
            namespace[k] = v
        print(namespace)

        return super().__new__(mcls, name, bases, namespace)


class Subset(metaclass=MakeSubset, parent=A, fields=['id', 'name']):
    ...


if __name__ == '__main__':  # 简单运行示例
    s = Subset(id=1, name='test')
    print(Subset.model_fields)
    print(s)