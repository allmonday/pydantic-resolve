import time
import math
from typing import List
from typing_extensions import TypedDict
from uuid import uuid1

class Performance():
    def __init__(self):
        self.full_path_timer = {}
    
    def get_timer(self, path: List[str]):
        key = '.'.join(path)
        if key not in self.full_path_timer:
            self.full_path_timer[key] = Timer(key)
        return self.full_path_timer[key]
    
    def __repr__(self) -> str:
        output = []
        for k, v in self.full_path_timer.items():
            output.append(f'{k}: {v}')
        return '\n'.join(output)
    

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
        t = time.time() - start

        self.records.append(t)
        self._max = max(self._max, t)
        self._min = min(self._min, t)
    
    @property
    def average(self):
        return sum(self.records) / len(self.records)
    
    @property
    def max(self):
        return self._max
    
    @property
    def min(self):
        return self._min
    
    def __hash__(self):
        return self.name
    
    def __repr__(self) -> str:
        return f'avg: {self.average:.4f}s, min: {self.min:.4f}s, max: {self.max:.4f}s'