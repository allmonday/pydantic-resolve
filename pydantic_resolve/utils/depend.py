from typing import Any, Callable, Optional
from aiodataloader import DataLoader

class Depends:
    def __init__(
        self,
        dependency: Optional[Callable[..., Any]] = None,
    ):
        self.dependency = dependency


def LoaderDepend(  # noqa: N802
    dependency: Optional[Callable[..., Any]] = None,
) -> DataLoader:
    return Depends(dependency=dependency)


Loader = LoaderDepend