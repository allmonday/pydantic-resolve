import inspect
from typing import Any, Callable, Optional
import pytest

def test_pydantic_version():
    from pydantic.version import VERSION
    assert VERSION.startswith('1.')

# verify the Feasibility of implement depends 
class Loader:
    def load(self):
        print('load')

def Depend(  # noqa: N802
    dependency: Optional[Callable[..., Any]] = None 
) -> Any:
    return Depends(dependency=dependency)

class Depends:
    def __init__(
        self, dependency: Optional[Callable[..., Any]] = None
    ):
        self.dependency = dependency

class LoaderA(Loader):
    def load(self):
        print('load-a')

class TestClass:
    def resolve(self, loader = Depend(LoaderA)):
        loader.load()

def runner_maker():
    cache = {}
    counter = {
        "init_count": 0
    }

    def exec(t_method):
        signature = inspect.signature(t_method)
        params = {}

        for k, v in signature.parameters.items():
            if v.default == inspect._empty:
                continue

            if isinstance(v.default, Depends):
                cache_key = v.default.dependency.__name__
                hit = cache.get(cache_key)
                if hit:
                    instance = hit
                else:
                    instance = v.default.dependency()
                    cache[cache_key] = instance
                    counter["init_count"] += 1
                params[k] = instance
        t_method(**params)
        return counter
    return exec

@pytest.mark.asyncio
async def test_depend():
    run = runner_maker()
    t = TestClass()
    t2 = TestClass()
    t3 = TestClass()

    run(t.resolve)   # missing
    run(t2.resolve)  # hit
    counter = run(t3.resolve)  # hit

    assert counter["init_count"] == 1