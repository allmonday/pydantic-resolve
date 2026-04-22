from typing import Any
from pydantic_resolve.exceptions import GlobalLoaderFieldOverlappedError


def merge_dicts(a: dict[str, Any], b: dict[str, Any]):
    overlap = set(a.keys()) & set(b.keys())
    if overlap:
        raise GlobalLoaderFieldOverlappedError(f'loader_params and global_loader_param have duplicated key(s): {",".join(overlap)}')
    else:
        return {**a, **b}