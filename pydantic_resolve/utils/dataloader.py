from collections import defaultdict
from typing import Callable, DefaultDict, Iterator, List, Mapping, Optional, Sequence, TypeVar
from aiodataloader import DataLoader

T = TypeVar("T")
V = TypeVar("V")

def build_list(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> Iterator[List[T]]:
    """
    helper function to build return list data required by aiodataloader
    """
    dct: DefaultDict[V, List[T]] = defaultdict(list)
    for item in items:
        _key = get_pk(item)
        dct[_key].append(item)
    results = (dct.get(k, []) for k in keys)
    return results


def build_object(items: Sequence[T], keys: List[V], get_pk: Callable[[T], V]) -> Iterator[Optional[T]]:
    """
    helper function to build return object data required by aiodataloader
    """
    dct: Mapping[V, T] = {}
    for item in items:
        _key = get_pk(item)
        dct[_key] = item
    results = (dct.get(k, None) for k in keys)
    return results


def copy_dataloader_kls(name, loader_kls):
    """
    quickly copy from an existed DataLoader class
    usage:
    SeniorMemberLoader = copy_dataloader('SeniorMemberLoader', ul.UserByLevelLoader)
    JuniorMemberLoader = copy_dataloader('JuniorMemberLoader', ul.UserByLevelLoader)
    """
    return type(name, loader_kls.__bases__, dict(loader_kls.__dict__))


class StrictEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        """it should not be triggered, otherwise will raise Exception"""
        raise ValueError('EmptyLoader should load from pre loaded data')


class ListEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        dct = {}
        return [dct.get(k, []) for k in keys]


class SingleEmptyLoader(DataLoader):
    async def batch_load_fn(self, keys):
        dct = {}
        return [dct.get(k, None) for k in keys]


def generate_strict_empty_loader(name):
    """generated Loader will raise ValueError if not found"""
    return type(name, StrictEmptyLoader.__bases__, dict(StrictEmptyLoader.__dict__))  #noqa


def generate_list_empty_loader(name):
    """generated Loader will return [] if not found"""
    return type(name, ListEmptyLoader.__bases__, dict(ListEmptyLoader.__dict__))  #noqa


def generate_single_empty_loader(name):
    """generated Loader will return None if not found"""
    return type(name, SingleEmptyLoader.__bases__, dict(SingleEmptyLoader.__dict__))  #noqa