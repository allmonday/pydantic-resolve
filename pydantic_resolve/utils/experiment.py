from typing import Callable, Type


def replace_method(cls: Type, cls_name: str, func_name: str, func: Callable):
    """test-only"""
    KLS = type(cls_name, (cls,), {func_name: func})
    return KLS