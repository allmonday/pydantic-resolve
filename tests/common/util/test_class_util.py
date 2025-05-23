from pydantic_resolve.utils.class_util import find_loop_members


def test_find_loop_members():
    # Test case 1: No loop members
    parent = ['a', 'b', 'c']
    name = 'd'
    result = find_loop_members(parent, name)
    assert result == []

    # Test case 2: Loop members present
    parent = ['a', 'b', 'c', 'd']
    name = 'a'
    result = find_loop_members(parent, name)
    assert result == ['a', 'b', 'c', 'd']

    # Test case 3: Loop members present
    parent = ['x', 'a', 'b', 'c', 'd']
    name = 'a'
    result = find_loop_members(parent, name)
    assert result == ['a', 'b', 'c', 'd']

    parent = ['a']
    name = 'a'
    result = find_loop_members(parent, name)
    assert result == ['a']