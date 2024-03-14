from pydantic import BaseModel
from pydantic_resolve.core import _scan_post_method

def test_scan_post_method_1():
    class A(BaseModel):
        a: str
        def post_a(self):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a)

    assert result == {
        'context': False,
        'ancestor_context': False,
    }


def test_scan_post_method_2():
    class A(BaseModel):
        a: str
        def post_a(self, context, ancestor_context):
            return 2 * self.a
        
    result = _scan_post_method(A.post_a)

    assert result == {
        'context': True,
        'ancestor_context': True,
    }

