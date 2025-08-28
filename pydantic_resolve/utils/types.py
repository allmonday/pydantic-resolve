from typing import Type, Union, List
try:  # Python 3.10+ provides PEP 604 unions using types.UnionType
    from types import UnionType as _UnionType
except ImportError:  # pragma: no cover - prior to 3.10
    _UnionType = ()  # sentinel so membership tests still work
from pydantic_resolve.compat import PYDANTIC_V2, OVER_PYTHON_3_7

if OVER_PYTHON_3_7:
    from typing import get_origin, get_args


def _is_optional_3_7(annotation):
    annotation_origin = getattr(annotation, "__origin__", None)
    return (
        annotation_origin == Union
        and len(getattr(annotation, "__args__", ())) == 2
        and (
            annotation.__args__[1] is type(None)  # noqa: E721
            or annotation.__args__[0] is type(None)  # noqa: E721
        )
    )


def _is_optional_3_x(annotation):
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Union and type(None) in args:
        return True
    return False


_is_optional = _is_optional_3_x if OVER_PYTHON_3_7 else _is_optional_3_7
_get_origin = get_origin if OVER_PYTHON_3_7 else lambda x: getattr(x, "__origin__", None)
_get_args = get_args if OVER_PYTHON_3_7 else lambda x: getattr(x, "__args__", ())


def _is_list(annotation):
    return _get_origin(annotation) in (list, List)


def shelling_type(tp):
    while _is_optional(tp) or _is_list(tp):
        tp = tp.__args__[0]
    return tp


def get_core_types(tp):
    """
    - get the core type
    - always return a tuple of core types
    """
    if tp is type(None):
        return tuple()

    # 1. Unwrap list layers
    def _shell_list(_tp):
        while _is_list(_tp):
            args = getattr(_tp, "__args__", ())
            if args:
                _tp = args[0]
            else:
                break
        return _tp
    
    tp = _shell_list(tp)

    if tp is type(None): # check again
        return tuple()

    while True:
        orig = _get_origin(tp)

        if orig in (Union, _UnionType):
            args = list(_get_args(tp))
            non_none = [a for a in args if a is not type(None)]  # noqa: E721
            has_none = len(non_none) != len(args)
            # Optional[T] case -> keep unwrapping (exactly one real type + None)
            if has_none and len(non_none) == 1:
                tp = non_none[0]
                tp = _shell_list(tp)
                continue
            # General union: return all non-None members (order preserved)
            if non_none:
                return tuple(non_none)
            return tuple()
        break

    # single concrete type
    return (tp,)


def get_class_field_annotations(cls: Type):
    anno = cls.__dict__.get('__annotations__') or {}
    return anno.keys()


def _get_type_v1(v):
    return v.type_


def _get_type_v2(v):
    return v.annotation


get_type = _get_type_v2 if PYDANTIC_V2 else _get_type_v1
