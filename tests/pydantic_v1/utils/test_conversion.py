import pytest
from dataclasses import dataclass
from typing import List, Optional, Union
from pydantic import BaseModel, ValidationError, Field
from pydantic_resolve.utils.conversion import try_parse_data_to_target_field_type_v1


# Test models for Union testing
class A(BaseModel):
    id: int

class B(BaseModel):
    name: str

class C(BaseModel):
    id: int
    name: str

class D(BaseModel):
    id: int
    name: str
    age: int

class SampleModel(BaseModel):
    union_object: Union[A, B] 
    union_object2: Union[C, D]
    class Config:
        smart_union = True


class TestTryParseDataToTargetFieldTypeV1:
    """Test cases for try_parse_data_to_target_field_type_v1 function"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.test_model = SampleModel(
            union_object=A(id=1),
            union_object2=C(id=1, name="name")
        )

    def test_pydantic_union_object_fields(self):
        """
        A and B has totally different fields, so it works
        """
        # Test Union[A, B] with B data (has name field)
        result = try_parse_data_to_target_field_type_v1(
            self.test_model, "union_object", dict(name='hello') 
        )
        assert result == B(name="hello")
        assert isinstance(result, B)
        
        # Test Union[A, B] with A data (has id field)
        result = try_parse_data_to_target_field_type_v1(
            self.test_model, "union_object", dict(id=123) 
        )
        assert result == A(id=123)
        assert isinstance(result, A)

    def test_pydantic_union_object2(self):
        """
        it parse from left to right by Union[A, B, C] order, and smart_union not workds
        """
        result = try_parse_data_to_target_field_type_v1(
            self.test_model, "union_object2", dict(id=1, name='hello', age=21) 
        )
        assert result != D(id=1, name='hello', age=21)
        assert isinstance(result, C)
        
        # Test Union[D, C] with C data (has id, name fields only)
        result = try_parse_data_to_target_field_type_v1(
            self.test_model, "union_object2", dict(id=1, name='hello') 
        )
        assert result == C(id=1, name='hello')
        assert isinstance(result, C)