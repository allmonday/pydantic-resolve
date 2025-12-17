import abc
from dataclasses import dataclass
from typing import Any, List, Union, Tuple, Iterator, Type
import pydantic_resolve.constant as const

@dataclass
class SendToInfo:
    collector_name: str | Tuple[str]

def SendTo(name: str| Tuple[str]) -> SendToInfo:
    return SendToInfo(collector_name=name)


def pre_generate_collector_config(kls):
    """
    iterrate kls fields, check and collect field who's annotated metadata for SendTo exists
    if kls's const.COLLECTOR_CONFIGURATION exists and the fields is not empty, raise exception
    group those field name based on collector_name, if single, leave it as str, else make it tuple
    then generate the configuration such as 
    { (field_a, field_b): collector_name } or ( field_a: collector_name })
    and set it into kls's const.COLLECTOR_CONFIGURATION
    """
    fields = list(_get_pydantic_field_items_with_send_to(kls))
    if not fields:
        return

    if hasattr(kls, const.COLLECTOR_CONFIGURATION):
        raise AttributeError(
            f"{const.COLLECTOR_CONFIGURATION} already exists; cannot use SendTo annotations at the same time"
        )

    grouped: dict[object, list[str]] = {}
    for field_name, meta in fields:
        grouped.setdefault(meta.collector_name, []).append(field_name)

    collect_dict: dict[object, object] = {}
    for collector_name, field_names in grouped.items():
        key: object = field_names[0] if len(field_names) == 1 else tuple(field_names)
        collect_dict[key] = collector_name

    setattr(kls, const.COLLECTOR_CONFIGURATION, collect_dict)

def _get_pydantic_field_items_with_send_to(kls) -> Iterator[Tuple[str, SendToInfo, Type]]:
    items = kls.model_fields.items()

    for name, v in items:
        metadata = v.metadata
        for meta in metadata:
            if isinstance(meta, SendToInfo):
                yield name, meta

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