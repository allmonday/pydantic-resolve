from dataclasses import dataclass
from typing import Type, TypeVar, Any, Callable, Optional
from pydantic import BaseModel
from aiodataloader import DataLoader


@dataclass
class Relationship:
    field: str
    target_kls: Any
    loader: Callable

@dataclass
class ErConfig:
    kls: Type[BaseModel]
    relationships: list[Relationship]


@dataclass
class LoaderInfo:
    by: str


def LoadBy(key: str) -> LoaderInfo:
    return LoaderInfo(by=key)