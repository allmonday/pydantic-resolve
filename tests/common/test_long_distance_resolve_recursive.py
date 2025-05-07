from pydantic import BaseModel
from pydantic_resolve.analysis import scan_and_store_metadata

class Tree(BaseModel):
    a: 'Tree'
    b: 'Tree'


# this is known issue
# self reference will not support early skip traversal.
def test_long_distance_resolve():
    result = scan_and_store_metadata(Tree)
    prefix = 'tests.common.test_long_distance_resolve_recursive'
    expect = {
        f'{prefix}.Tree': {
            'resolve': [],
            'post': [],
            'object_fields': ['a', 'b'],
            'expose_dict': {},
            'collect_dict': {},
        }
    }
    # from pprint import pprint
    # pprint(result)
    for k, v in result.items():
        assert expect[k].items() <= v.items()