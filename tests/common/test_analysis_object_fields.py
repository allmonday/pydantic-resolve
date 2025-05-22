from pydantic import BaseModel
from pydantic_resolve.analysis import scan_and_store_metadata
from typing import Optional

# case 1
class Tree(BaseModel):
    a: Optional['Tree']
    b: Optional['Tree']
    def resolve_b(self):
        return self.b

# case 2
class Tree2(BaseModel):
    t: Optional['Tree2']


# case 3
class Tree32(BaseModel):
    t: Optional['Tree31']
    def resolve_t(self):
        return self.t

class Tree31(BaseModel):
    t: Optional[Tree32]

# root
class Kls(BaseModel):
    tree: Tree
    tree2: Tree2
    tree3: Tree31 # 31 -> 32 -> 31 -> ...

# this is known issue
# self reference will not support early skip traversal.
def test_analysis_object_fields():
    result = scan_and_store_metadata(Tree)
    prefix = 'tests.common.test_analysis_object_fields'
    expect = {
        f'{prefix}.Kls': {
            'resolve': [],
            'post': [],
            'object_fields': ['tree', 'tree3'],
            'expose_dict': {},
            'collect_dict': {},
        },
        f'{prefix}.Tree': {
            'resolve': ['resolve_b'],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
        },
        f'{prefix}.Tree2': {
            'resolve': [],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
        }, 
        f'{prefix}.Tree31': {
            'resolve': [],
            'post': [],
            'object_fields': ['t'],
            'expose_dict': {},
            'collect_dict': {},
        },
        f'{prefix}.Tree32': {
            'resolve': ['resolve_t'],
            'post': [],
            'object_fields': [],
            'expose_dict': {},
            'collect_dict': {},
        },
    }
    from pprint import pprint
    pprint(result)
    for k, v in result.items():
        assert expect[k].items() <= v.items()