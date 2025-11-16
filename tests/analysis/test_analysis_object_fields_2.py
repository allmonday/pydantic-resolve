from pydantic import BaseModel
from pydantic_resolve.analysis import Analytic
from typing import Optional

# ┌─────┐          
# │ Kls │          
# └─┬───┘          
#   │              
#   │              
#   │              
#   │              
#   │              
# ┌─▼──────┐       
# │ Tree31 ◄──────┐
# └─┬──────┘      │
#   │             │
#   │             │
#   │             │
#   │             │
# ┌─▼──────┐      │
# │ Tree32 ├──────┘
# └─┬──────┘       
#   │  [end, t]            
#   │              
#   │              
#   │              
#  ┌▼───┐          
#  │End │ (has resolve)
#  └────┘          

# 1. tests.common.test_analysis_object_fields_2.Kls
# 1. tests.common.test_analysis_object_fields_2.Tree31
# 1. tests.common.test_analysis_object_fields_2.Tree32
# 1. tests.common.test_analysis_object_fields_2.End
# 2. tests.common.test_analysis_object_fields_2.Tree32 end True
# 1. tests.common.test_analysis_object_fields_2.Tree31
# ---- hit
# hit, other_loop_members ['tests.common.test_analysis_object_fields_2.Tree32']
# check loop ember
# tests.common.test_analysis_object_fields_2.Tree32
# {'resolve': [], 'resolve_params': {}, 'post': [], 'post_params': {}, 'post_default_handler_params': None, 'object_fields': ['end', 't'], 'expose_dict': {}, 'collect_dict': {}, 'kls': <class 'tests.common.test_analysis_object_fields_2.Tree32'>, 'has_context': False, 'should_traverse': None}
# 
# ------------- End should affact the Tree32 to be traversed. ---------------
# 
# 2. tests.common.test_analysis_object_fields_2.Tree32 t False
# 2. tests.common.test_analysis_object_fields_2.Tree31 t True
# 2. tests.common.test_analysis_object_fields_2.Kls tree3 True
# 

# case 3
class Tree32(BaseModel):
    end: 'End'
    t: Optional['Tree31']

class Tree31(BaseModel):
    t: Optional[Tree32]

class End(BaseModel):
    a: str
    def resolve_a(self):
        return self.a

# root
class Kls(BaseModel):
    tree3: Tree31 # 31 -> 32 -> 31 -> ...


# this is known issue
# self reference will not support early skip traversal.
def test_analysis_object_fields():
    result = Analytic().scan(Kls)
    prefix = 'tests.analysis.test_analysis_object_fields_2'
    expect = {
        f'{prefix}.Kls': {
            'resolve': [],
            'object_fields': ['tree3'],
            'should_traverse': True,
        },
        f'{prefix}.Tree31': {
            'resolve': [],
            'object_fields': ['t'],
            'should_traverse': True,
        },
        f'{prefix}.Tree32': {
            'resolve': [],
            'object_fields': ['end', 't'],
            'should_traverse': True,
        },
        f'{prefix}.End': {
            'resolve': ['resolve_a'],
            'object_fields': [],
            'should_traverse': True,
        },
    }
    from pprint import pprint
    pprint(result)
    for k, v in result.items():
        assert expect[k].items() <= v.items()