from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import List, Optional
from pydantic import parse_obj_as

"""
in contrast to pydantic, dataclass does not need update forward refs
"""

@dataclass
class A():
    name: str
    a: Optional[A]
    b: Optional[B]

@dataclass
class B():
    name: str
    c: List[C] = field(default_factory=list)

@dataclass
class C():
    name: str


t = time.time()
c = parse_obj_as(B, {'name': 'ki', 'c': [{'name': '1'}]})
c = parse_obj_as(B, c)
print(c)