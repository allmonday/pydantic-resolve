import pytest
from aiodataloader import DataLoader
from pydantic import BaseModel
from pydantic_resolve.analysis import _scan_resolve_method
from pydantic_resolve import LoaderDepend, Collector

def test_scan_resolve_method_1():
    class A(BaseModel):
        a: str
        def resolve_a(self):
            return 2 * self.a
        
    result = _scan_resolve_method(A.resolve_a, 'resolve_a')

    assert result == {
        'trim_field': 'a',
        'context': False,
        'ancestor_context': False,
        'parent': False,
        'dataloaders': []
    }


def test_scan_resolve_method_2():
    class A(BaseModel):
        a: str
        def resolve_a(self, context, ancestor_context, parent):
            return 2 * self.a
        
    result = _scan_resolve_method(A.resolve_a, 'resolve_a')

    assert result == {
        'trim_field': 'a',
        'context': True,
        'ancestor_context': True,
        'parent': True,
        'dataloaders': []
    }


def test_scan_resolve_method_3():
    class Loader(DataLoader):
        async def batch_loader_fn(self, keys):
            return keys

    class A(BaseModel):
        a: str
        def resolve_a(self, context, ancestor_context, parent, loader=LoaderDepend(Loader)):
            return 2 * self.a
        
    result = _scan_resolve_method(A.resolve_a, 'resolve_a')

    assert result == {
        'trim_field': 'a',
        'context': True,
        'ancestor_context': True,
        'parent': True,
        'dataloaders': [
            {
                'param': 'loader',
                'kls': Loader,
                'path': 'test_scan_resolve_method.test_scan_resolve_method_3.<locals>.Loader' 
            }
        ]
    }


def test_scan_resolve_method_4():
    class A(BaseModel):
        a: str
        def resolve_a(self, c=Collector('some_field')):
            return c.values()
        
    with pytest.raises(AttributeError):
        _scan_resolve_method(A.resolve_a, 'resolve_a')
