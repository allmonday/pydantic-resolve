from typing import Any, Callable, Optional

class Depends:
    def __init__(
        self,
        dependency: Optional[Callable[..., Any]] = None,
    ):
        self.dependency = dependency


def LoaderDepend(  # noqa: N802
    dependency: Optional[Callable[..., Any]] = None,
) -> Any:
    return Depends(dependency=dependency)