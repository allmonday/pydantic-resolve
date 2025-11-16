from typing import Type, Union, List, Annotated
try:  # Python 3.10+ provides PEP 604 unions using types.UnionType
    from types import UnionType as _UnionType
except ImportError:  # pragma: no cover - prior to 3.10
    _UnionType = ()  # sentinel so membership tests still work

# Python <3.12 compatibility: TypeAliasType exists only from 3.12 (PEP 695)
try:  # pragma: no cover - import guard
    from typing import TypeAliasType  # type: ignore
except Exception:  # pragma: no cover
    class _DummyTypeAliasType:  # minimal sentinel so isinstance checks are safe
        pass
    TypeAliasType = _DummyTypeAliasType  # type: ignore

from typing import get_origin, get_args


def _is_optional(annotation):
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Union and type(None) in args:
        return True
    return False


def _is_list(annotation):
    return get_origin(annotation) in (list, List)


def shelling_type(tp):
    while _is_optional(tp) or _is_list(tp):
        tp = tp.__args__[0]
    return tp


def get_core_types(tp):
    """
    - get the core type
    - always return a tuple of core types
    """
    # Helpers
    def _unwrap_alias(t):
        """Unwrap PEP 695 type aliases by following __value__ repeatedly."""
        while isinstance(t, TypeAliasType) or (
            t.__class__.__name__ == 'TypeAliasType' and hasattr(t, '__value__')
        ):
            try:
                t = t.__value__
            except Exception:  # pragma: no cover - defensive
                break
        return t

    def _enqueue(items, q):
        for it in items:
            if it is not type(None):  # skip None in unions
                q.append(it)

    # Queue-based shelling to reach concrete core types
    queue: list[object] = [tp]
    result: list[object] = []

    while queue:
        cur = queue.pop(0)
        if cur is type(None):
            continue

        cur = _unwrap_alias(cur)

        # Handle Annotated[T, ...] as a shell
        if get_origin(cur) is Annotated:
            args = get_args(cur)
            if args:
                queue.append(args[0])
            continue

        # Handle Union / Optional / PEP 604 UnionType
        orig = get_origin(cur)
        if orig in (Union, _UnionType):
            args = get_args(cur)
            # push all non-None members back for further shelling
            _enqueue(args, queue)
            continue

        # Handle list shells
        if _is_list(cur):
            args = getattr(cur, "__args__", ())
            if args:
                queue.append(args[0])
            continue

        # If still an alias-like wrapper, unwrap again and re-process
        _cur2 = _unwrap_alias(cur)
        if _cur2 is not cur:
            queue.append(_cur2)
            continue

        # Otherwise treat as a concrete core type (could be a class, typing.Final, etc.)
        result.append(cur)

    return tuple(result)


def get_class_field_annotations(cls: Type):
    anno = cls.__dict__.get('__annotations__') or {}
    return anno.keys()


def get_type(v):
    return v.annotation


