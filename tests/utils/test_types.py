from pydantic_resolve.utils.types import (
    _is_optional, 
    _is_list,
    get_core_types, 
    shelling_type,
    get_class_field_annotations,
    _is_optional
)
from typing import Optional, Union, List, Dict, Tuple, Set
import pytest

@pytest.mark.parametrize(
    "annotation,expected",
    [
        (Optional[int], True),
        (Union[int, None], True),
        (Union[None, int], True),
        (int, False),
        (List[int], False),
        (Union[int, str], False),
        (Union[int, str, None], True),  # Union with None
        (Union[None, int, str], True),  # None at the beginning
    ]
)
def test_is_optional(annotation, expected):
    assert _is_optional(annotation) == expected


@pytest.mark.parametrize(
    "annotation,expected",
    [
        (List[int], True),
        (List[str], True),
        (List[Optional[int]], True),
        (int, False),
        (Optional[int], False),
        (Union[int, str], False),
        (Dict[str, int], False),
        (Tuple[int, str], False),
        (Set[int], False),
    ]
)
def test_is_list(annotation, expected):
    assert _is_list(annotation) == expected


@pytest.mark.parametrize(
    "tp,expected",
    [
        # Basic types
        (int, (int,)),
        (str, (str,)),
        (float, (float,)),
        
        # Optional types
        (Optional[int], (int,)),
        (Union[int, None], (int,)),
        (Union[None, int], (int,)),
        
        # List types
        (List[int], (int,)),
        (List[str], (str,)),
        (List[Optional[int]], (int,)),
        
        # Nested list types
        (List[List[int]], (int,)),
        (List[List[Optional[str]]], (str,)),
        
        # Union types (multiple non-None types)
        (Union[int, str], (int, str)),
        (Union[int, str, float], (int, str, float)),
        (Union[str, int], (str, int)),  # Order matters
        
        # Union with None
        (Union[int, str, None], (int, str)),
        (Union[None, int, str], (int, str)),
        (Union[int, None, str], (int, str)),
        
        # Complex nested types
        (Optional[List[int]], (int,)),
        (List[Union[int, str]], (int, str)),
        (Optional[List[Union[int, str]]], (int, str)),
        
        # Edge cases
        (Union[None], ()),  # Only None
        (List[Union[None]], ()),  # List of only None
    ]
)
def test_get_core_types(tp, expected):
    result = get_core_types(tp) 
    assert result == expected


@pytest.mark.parametrize(
    "tp,expected",
    [
        # Basic unwrapping
        (Optional[int], int),
        (List[int], int),
        (Optional[List[int]], int),
        (List[Optional[int]], int),
        
        # Nested structures
        (List[List[int]], int),
        (Optional[List[List[str]]], str),
        
        # Simple types
        (int, int),
        (str, str),
    ]
)
def test_shelling_type(tp, expected):
    assert shelling_type(tp) == expected


def test_get_class_field_annotations():
    class TestClass:
        field1: int
        field2: str
        field3: Optional[float]
    
    annotations = get_class_field_annotations(TestClass)
    expected_fields = {'field1', 'field2', 'field3'}
    assert set(annotations) == expected_fields


def test_get_class_field_annotations_empty():
    class EmptyClass:
        pass
    
    annotations = get_class_field_annotations(EmptyClass)
    assert list(annotations) == []


def test_get_class_field_annotations_with_inheritance():
    class BaseClass:
        base_field: int
    
    class DerivedClass(BaseClass):
        derived_field: str
    
    # Should only get annotations from the specific class, not inherited ones
    base_annotations = get_class_field_annotations(BaseClass)
    derived_annotations = get_class_field_annotations(DerivedClass)
    
    assert set(base_annotations) == {'base_field'}
    assert set(derived_annotations) == {'derived_field'}


def test_is_optional_compatibility():
    """Test that _is_optional works correctly across Python versions"""
    assert _is_optional(Optional[int]) == True
    assert _is_optional(Union[int, None]) == True
    assert _is_optional(Union[None, int]) == True
    assert _is_optional(int) == False
    assert _is_optional(List[int]) == False
    assert _is_optional(Union[int, str]) == False


# Additional edge case tests
def test_complex_nested_types():
    """Test complex nested type scenarios"""
    # Triple nested
    nested_type = List[List[List[int]]]
    assert get_core_types(nested_type) == (int,)
    
    # Mixed nesting with Optional
    mixed_type = Optional[List[Optional[List[Optional[int]]]]]
    assert get_core_types(mixed_type) == (int,)
    
    # Union in List
    union_in_list = List[Union[int, str, None]]
    assert get_core_types(union_in_list) == (int, str)


def test_union_edge_cases():
    """Test edge cases for Union types"""
    # Union with duplicate types (if this is valid in your type system)
    # Note: This might not be a real scenario, but testing robustness
    
    # Multiple None types (edge case)
    single_none = Union[type(None)]
    result = get_core_types(single_none)
    assert result == () or result == (type(None),)  # Depending on implementation
    
    # Large Union
    large_union = Union[int, str, float, bool, bytes]
    assert len(get_core_types(large_union)) == 5


@pytest.mark.parametrize(
    "annotation",
    [
        Dict[str, int],
        Tuple[int, str],
        Set[int],
        # Add more complex types if needed
    ]
)
def test_non_list_container_types(annotation):
    """Test that non-list container types are not treated as lists"""
    assert _is_list(annotation) == False
    # These should return as single types
    assert get_core_types(annotation) == (annotation,)
