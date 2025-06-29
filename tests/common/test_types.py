from pydantic_resolve.utils.types import _is_optional_3_x
from typing import Optional, Union, List
import pytest
import sys

@pytest.mark.parametrize(
    "annotation,expected",
    [
        (Optional[int], True),
        (Union[int, None], True),
        (Union[None, int], True),
        (int, False),
        (List[int], False),
        (Union[int, str], False),
    ]
)
@pytest.mark.skipif(sys.version_info == (3, 7), reason="This test is for Python 3.8 and higher")
def test_is_optional_3_x(annotation, expected):
    assert _is_optional_3_x(annotation) == expected

