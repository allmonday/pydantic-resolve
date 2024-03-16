from pydantic import BaseModel
from pydantic_resolve.core import _scan_post_method
from pydantic_resolve import Collector

def test_scan_post_method_1():
    class A(BaseModel):
        a: str
        def post_a(self):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a, 'post_a')

    assert result == {
        'trim_field': 'a',
        'context': False,
        'ancestor_context': False,
        'collectors': []
    }


def test_scan_post_method_2():
    class A(BaseModel):
        a: str
        def post_a(self, context, ancestor_context):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a, 'post_a')

    assert result == {
        'trim_field': 'a',
        'context': True,
        'ancestor_context': True,
        'collectors': []
    }


def test_scan_post_method_3():
    class A(BaseModel):
        a: str
        def post_a(self, context, ancestor_context, collector=Collector(alias='c_name')):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a, 'post_a')

    assert len(result['collectors']) == 1
    assert result['collectors'][0]['field'] == 'post_a' 
    assert result['collectors'][0]['param'] == 'collector' 
    assert result['collectors'][0]['alias'] == 'c_name'
    assert isinstance(result['collectors'][0]['instance'], Collector)

