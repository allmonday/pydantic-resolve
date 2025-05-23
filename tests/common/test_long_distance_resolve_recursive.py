from pydantic import BaseModel
from pydantic_resolve.analysis import scan_and_store_metadata

class Tree(BaseModel):
    a: 'Tree'
    b: 'Tree'

class Tree2(BaseModel):
    a: 'Tree2'
    b: 'Tree2'
    def resolve_b(self):
        return self.b

def test_long_distance_resolve():
    result = scan_and_store_metadata(Tree)
    prefix = 'tests.common.test_long_distance_resolve_recursive'
    expect = {
        f'{prefix}.Tree': {
            'resolve': [],
            'object_fields': [],
            'should_traverse': False,
        }
    }
    # from pprint import pprint
    # pprint(result)
    for k, v in result.items():
        assert expect[k].items() <= v.items()

def test_long_distance_resolve_2():
    result = scan_and_store_metadata(Tree2)
    prefix = 'tests.common.test_long_distance_resolve_recursive'
    expect = {
        f'{prefix}.Tree2': {
            'resolve': ['resolve_b'],
            'object_fields': ['a'],
            'should_traverse': True,
        }
    }
    # from pprint import pprint
    # pprint(result)
    for k, v in result.items():
        assert expect[k].items() <= v.items()