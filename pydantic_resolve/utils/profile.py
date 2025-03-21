import time
import math
from typing import List
from uuid import uuid1
from pydantic_resolve.utils.logger import get_logger

profile_logger = get_logger(__name__)

class Profile():
    def __init__(self):
        self.full_path_timer = {}
    
    def get_timer(self, path: List[str]):
        key = '.'.join(path)
        if key not in self.full_path_timer:
            self.full_path_timer[key] = Timer(key)
        return self.full_path_timer[key]
    
    def __repr__(self) -> str:
        def format_key(key, longest):
            return key + ' ' * (longest - len(key))

        longest = max([len(key) for key in self.full_path_timer.keys()])
        items = self.full_path_timer.items()
        items = sorted(items, key=lambda x: x[0])
        items = [f'{format_key(item[0], longest)}: {item[1]}' for item in items]
        return '\n'.join(items)
    
    def report(self):
        profile_logger.debug('\n' + self.__repr__())
    

class Timer():
    def __init__(self, name: str):
        self.name = name
        self._max = 0
        self._min = math.inf
        self.timeset = {} 
        self.records = []
    
    def start(self):
        id = uuid1()
        self.timeset[id] = time.time()
        return id
    
    def end(self, id: str):
        start = self.timeset[id]
        t = self.to_ms(time.time() - start)

        self.records.append(t)
        self._max = max(self._max, t)
        self._min = min(self._min, t)
    
    @property
    def average(self):
        try: 
            return sum(self.records) / len(self.records)
        except ZeroDivisionError:
            return 0
    
    @property
    def max(self):
        return self._max
    
    @property
    def min(self):
        return self._min
    
    def to_ms(self, t):
        return t * 1000
    
    def __repr__(self) -> str:
        return f'avg: {self.average:.1f}ms, max: {self.max:.1f}ms, min: {self.min:.1f}ms'