from pydantic import BaseModel
from pydantic_resolve.analysis import Analytic

class Tree(BaseModel):
    a: 'Tree'
    b: 'Tree'

class Tree2(BaseModel):
    a: 'Tree2'
    b: 'Tree2'
    def resolve_b(self):
        return self.b

def test_long_distance_resolve():
    result = Analytic().scan(Tree)
    prefix = 'tests.analysis.test_analysis_object_fields_3'
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
    result = Analytic().scan(Tree2)
    prefix = 'tests.analysis.test_analysis_object_fields_3'
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