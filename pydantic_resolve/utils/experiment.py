from typing import Callable, Type


def replace_method(cls: Type, cls_name: str, func_name: str, func: Callable):  # noqa: D401
    """test-only helper: 返回一个替换单个方法后的类型"""
    KLS = type(cls_name, (cls,), {func_name: func})
    return KLS
