import abc
from dataclasses import dataclass
from typing import Any, List, Union, Tuple

@dataclass
class SendToInfo:
    alias: str | Tuple[str]

def SendTo(alias: str| Tuple[str]) -> SendToInfo:
    return SendToInfo(alias=alias)

class ICollector(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(self, alias: str):
        self.alias = alias

    @abc.abstractmethod
    def add(self, val):
        """how to add new element(s)"""

    @abc.abstractmethod
    def values(self) -> Any:
        """get result"""


class Collector(ICollector):
    def __init__(self, alias: str, flat: bool=False):
        super().__init__(alias)
        self.flat = flat
        self.val = []

    def add(self, val: Union[Any, List[Any]]) -> None:
        if self.flat:
            if isinstance(val, list):
                self.val.extend(val)
            else:
                raise TypeError('if flat, target should be list')
        else:
            self.val.append(val)

    def values(self) -> List[Any]:
        return self.val