from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from aiodataloader import DataLoader

class Depends:
    def __init__(
        self,
        dependency: Optional[Callable[..., Any]] = None,
    ):
        self.dependency = dependency


def Loader(  # noqa: N802
    dependency: Optional[Callable[..., Any]] = None,
) -> "DataLoader":
    return Depends(dependency=dependency)
