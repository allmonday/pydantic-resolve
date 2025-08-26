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
    # Union types for testing
    union_object: Union[A, B] 
    union_smart: Union[D, C] = Field(union_smart=True)


class TestTryParseDataToTargetFieldTypeV1:
    """Test cases for try_parse_data_to_target_field_type_v1 function"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.test_model = SampleModel(
            union_object=A(id=1),
            union_smart=C(id=1, name="name")
        )

    def test_pydantic_union_object_fields(self):
        """Test union object fields for Pydantic models"""
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

    def test_pydantic_union_smart_fields(self):
        """Test union smart fields for Pydantic models"""
        # Test Union[D, C] with D data (has id, name, age fields)
        result = try_parse_data_to_target_field_type_v1(
            self.test_model, "union_smart", dict(id=1, name='hello', age=21) 
        )
        assert result == D(id=1, name='hello', age=21)
        assert isinstance(result, D)
        
        # Test Union[D, C] with C data (has id, name fields only)
        result = try_parse_data_to_target_field_type_v1(
            self.test_model, "union_smart", dict(id=1, name='hello') 
        )
        assert result == C(id=1, name='hello')
        assert isinstance(result, C)

    def test_validation_errors(self):
        """Test validation error handling for union fields"""
        # Invalid data that doesn't match any union type
        with pytest.raises(ValidationError):
            try_parse_data_to_target_field_type_v1(
                self.test_model, "union_object", {"invalid": "data"}
            )
        
        # Invalid data for union_smart
        with pytest.raises(ValidationError):
            try_parse_data_to_target_field_type_v1(
                self.test_model, "union_smart", {"invalid": "data"}
            )
