from pydantic import BaseModel
from pydantic_resolve.analysis import scan_and_store_metadata
from typing import Optional

# ┌────────┐                             
# │   Kls  │                             
# └────────┘                             
#     │       ┌─────────────────┐          
#     │       │ ┌──────────┐    │
#     │       ▼ ▼          │    │ 
#     │     ┌─────┐        x(o) o          
#     ├─o───│ Tree│────────┘    │          
#     │     └─────┘─────────────┘          
#     │                                  
#     │                                  
#     │         ┌───────┐                
#     │         │       │    
#     │         ▼       x               
#     │     ┌──────┐    │                
#     ├─x───│ Tree2│ ───┘                
#     │     └──────┘                     
#     │                                  
#     │         ┌─────────o─────────┐    
#     │         │                   │    
#     │         ▼                   │    
#     │     ┌───────┐           ┌───────┐
#     ├──o──│ Tree31│─────x────►│Tree32 │
#     │     └───────┘           └───────┘
#     │                                  
#     │         ┌───────┐                
#     │         │       │    
#     │         ▼       o               
#     │     ┌──────┐    │                
#     └─x───│ Tree4│ ───┘                
#           └──────┘                     
#
# o: should treverse
# x: should not treverse
#
# 1. traverse the class
# 2. add extra param: visited_parent in walker
# 3. if current class is visited before, fetch the loop members, 
#   add loops into loop collection, and mark it as mount point
# 4. if current class is visited before, but not in the loop member, ignore
# another point: walker should analysis the loop first


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


# case 4
class Tree4(BaseModel):
    t: Optional['Tree4']

    path: str = ''
    def resolve_path(self):
        return ''

# root
class Kls(BaseModel):
    tree: Tree
    tree2: Tree2
    tree3: Tree31 # 31 -> 32 -> 31 -> ...
    tree4: Tree4

# this is known issue
# self reference will not support early skip traversal.
def test_analysis_object_fields():
    result = scan_and_store_metadata(Kls)
    prefix = 'tests.common.test_analysis_object_fields_1'
    expect = {
        f'{prefix}.Kls': {
            'resolve': [],
            'object_fields': ['tree', 'tree3', 'tree4'],
            'should_traverse': True,
        },
        f'{prefix}.Tree': {
            'resolve': ['resolve_b'],
            'object_fields': ['a'],
            'should_traverse': True,
        },
        f'{prefix}.Tree2': {
            'resolve': [],
            'object_fields': [],
            'should_traverse': False,
        }, 
        f'{prefix}.Tree31': {
            'resolve': [],
            'object_fields': ['t'],
            'should_traverse': True,
        },
        f'{prefix}.Tree32': {
            'resolve': ['resolve_t'],
            'object_fields': [],
            'should_traverse': True,
        },
        f'{prefix}.Tree4': {
            'resolve': ['resolve_path'],
            'object_fields': ['t'],
            'should_traverse': True,
        },
    }
    # from pprint import pprint
    # pprint(result)
    for k, v in result.items():
        assert expect[k].items() <= v.items()