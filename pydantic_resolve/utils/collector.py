import abc
from typing import Any


class ICollector(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(self, alias: str):
        self.alias = alias  # required, must have

    @abc.abstractmethod
    def add(self, val):
        """how to add new element(s)"""

    @abc.abstractmethod
    def values(self) -> Any:
        """get result"""


class Collector(ICollector):
    def __init__(self, alias: str, flat: bool=False):
        self.alias = alias
        self.flat = flat
        self.val = []

    def add(self, val):
        if self.flat:
            if isinstance(val, list):
                self.val.extend(val)
            else:
                raise AttributeError('if flat, target should be list')
        else:
            self.val.append(val)

    def values(self):
        return self.val