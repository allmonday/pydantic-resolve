from typing import Type, Union
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


def _is_list(annotation):
    return getattr(annotation, "__origin__", None) == list


def shelling_type(tp):
    while _is_optional(tp) or _is_list(tp):
        tp = tp.__args__[0]
    return tp


def shelling_type2(tp):
    """
    - get the core type
    - always return a tuple of core types
    """
    # 1. Unwrap list layers
    while _is_list(tp):
        args = getattr(tp, "__args__", ())
        if args:
            tp = args[0]
        else:
            break

    # 2. Handle Optional / Union
    def _origin(x):
        return (
            get_origin(x)
            if OVER_PYTHON_3_7
            else getattr(x, "__origin__", None)
        )

    def _args(x):
        return get_args(x) if OVER_PYTHON_3_7 else getattr(x, "__args__", ())

    while True:
        orig = _origin(tp)
        if orig is Union:
            args = list(_args(tp))
            non_none = [a for a in args if a is not type(None)]  # noqa: E721
            has_none = len(non_none) != len(args)
            # Optional[T] case -> keep unwrapping
            if has_none and len(non_none) == 1:
                tp = non_none[0]
                continue
            # Union (with or without None) -> return tuple of real types
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
