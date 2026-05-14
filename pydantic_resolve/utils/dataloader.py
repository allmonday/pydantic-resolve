from collections import defaultdict
from typing import Callable, DefaultDict, Sequence, TypeVar
from aiodataloader import DataLoader

T = TypeVar("T")
V = TypeVar("V")

def build_list(items: Sequence[T], keys: list[V], get_pk: Callable[[T], V]) -> list[list[T]]:
    """
    helper function to build return list data required by aiodataloader
    """
    dct: DefaultDict[V, list[T]] = defaultdict(list)
    for item in items:
        _key = get_pk(item)
        dct[_key].append(item)
    return [dct.get(k, []) for k in keys]


def build_object(items: Sequence[T], keys: list[V], get_pk: Callable[[T], V]) -> list[T | None]:
    """
    helper function to build return object data required by aiodataloader
    """
    dct: dict[V, T] = {}
    for item in items:
        _key = get_pk(item)
        dct[_key] = item
    return [dct.get(k, None) for k in keys]


def copy_dataloader_kls(name, loader_kls):
    """
    quickly copy from an existing DataLoader class
    usage:
    SeniorMemberLoader = copy_dataloader('SeniorMemberLoader', ul.UserByLevelLoader)
    JuniorMemberLoader = copy_dataloader('JuniorMemberLoader', ul.UserByLevelLoader)
    """
    class NewLoader(loader_kls):
        pass
    NewLoader.__name__ = name
    NewLoader.__qualname__ = name
    return NewLoader


class StrictEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        """it should not be triggered, otherwise will raise Exception"""
        raise ValueError('EmptyLoader should load from pre loaded data')


class ListEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        return [[] for _ in keys]


class SingleEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        return [None for _ in keys]


def generate_strict_empty_loader(name):
    """generated Loader will raise ValueError if not found"""
    class NewLoader(StrictEmptyLoader):
        pass
    NewLoader.__name__ = name
    NewLoader.__qualname__ = name
    return NewLoader


def generate_list_empty_loader(name):
    """generated Loader will return [] if not found"""
    class NewLoader(ListEmptyLoader):
        pass
    NewLoader.__name__ = name
    NewLoader.__qualname__ = name
    return NewLoader


def generate_single_empty_loader(name):
    """generated Loader will return None if not found"""
    class NewLoader(SingleEmptyLoader):
        pass
    NewLoader.__name__ = name
    NewLoader.__qualname__ = name
    return NewLoader