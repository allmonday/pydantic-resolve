from typing import Any, Dict
from pydantic_resolve.exceptions import GlobalLoaderFieldOverlappedError


def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]):
    overlap = set(a.keys()) & set(b.keys())
    if overlap:
        raise GlobalLoaderFieldOverlappedError(f'loader_params and global_loader_param have duplicated key(s): {",".join(overlap)}')
    else:
        return {**a, **b}