from pydantic import BaseModel
from pydantic_resolve.analysis import _scan_post_method, _scan_post_default_handler
from pydantic_resolve import Collector

def test_scan_post_method_1():
    class A(BaseModel):
        a: str
        def post_a(self):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a, 'post_a', None)

    assert result == {
        'trim_field': 'a',
        'context': False,
        'ancestor_context': False,
        'parent': False,
        'dataloaders': [],
        'collectors': []
    }


def test_scan_post_method_2():
    class A(BaseModel):
        a: str
        def post_a(self, context, ancestor_context, parent):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a, 'post_a', None)

    assert result == {
        'trim_field': 'a',
        'context': True,
        'ancestor_context': True,
        'parent': True,
        'dataloaders': [],
        'collectors': []
    }


def test_scan_post_method_3():
    class A(BaseModel):
        a: str
        def post_a(self,
                   context,
                   ancestor_context,
                   collector=Collector(alias='c_name'),
                   collector_2=Collector(alias='c_name'),
                   ):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a, 'post_a', None)

    assert len(result['collectors']) == 2
    assert result['collectors'][0]['field'] == 'post_a' 
    assert result['collectors'][0]['param'] == 'collector' 
    assert result['collectors'][0]['alias'] == 'c_name'
    assert isinstance(result['collectors'][0]['instance'], Collector)

    assert result['collectors'][1]['field'] == 'post_a' 
    assert result['collectors'][1]['param'] == 'collector_2' 
    assert result['collectors'][1]['alias'] == 'c_name'
    assert isinstance(result['collectors'][1]['instance'], Collector)

def test_scan_post_method_4():
    class A(BaseModel):
        a: str
        def post_a(self, context, ancestor_context, collector=Collector(alias='c_name')):
            return 2 * self.a
        
        def post_default_handler(self, context, ancestor_context, parent):
            return 1
        
    result = _scan_post_default_handler(A.post_default_handler)

    assert result['context'] == True
    assert result['parent'] == True
    assert result['ancestor_context'] == True

