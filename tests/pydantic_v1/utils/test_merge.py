import pytest
from pydantic_resolve.utils.params import merge_dicts
from pydantic_resolve.exceptions import GlobalLoaderFieldOverlappedError


def test_merge_ok():
    a = dict(a=1)
    b = dict(b=1)

    assert merge_dicts(a, b) == {'a': 1, 'b': 1}

    a = dict()
    b = dict(b=1)

    assert merge_dicts(a, b) == {'b': 1}


def test_merge_oops():
    a = dict(a=1)
    b = dict(b=1, a=1)

    with pytest.raises(GlobalLoaderFieldOverlappedError):
        assert merge_dicts(a, b) == {'a': 1, 'b': 1}