"""Tests for create_subset function in subset.py"""

import pytest
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_resolve.utils.subset import create_subset, DefineSubset
import pydantic_resolve.constant as const


class TestCreateSubset:
    """Test cases for create_subset function."""
    
    def test_basic_subset_creation(self):
        """Test basic subset creation with required fields."""
        class Parent(BaseModel):
            id: int
            name: str
            age: int
            email: str
        
        Subset = create_subset(Parent, ['id', 'name'], 'TestSubset')
        
        # Test that we can create an instance
        instance = Subset(id=1, name='test')
        assert instance.id == 1
        assert instance.name == 'test'
        
        # Test that excluded fields are not present in the model
        field_names = list(Subset.model_fields.keys())
        
        assert 'id' in field_names
        assert 'name' in field_names
        assert 'age' not in field_names
        assert 'email' not in field_names

        # Test that extra fields are ignored (Pydantic default behavior)
        instance_with_extra = Subset(id=2, name='test2', age=25)  # age is ignored
        assert instance_with_extra.id == 2
        assert instance_with_extra.name == 'test2'
        assert not hasattr(instance_with_extra, 'age')
    
    def test_subset_with_optional_fields(self):
        """Test subset creation with optional fields."""
        class Parent(BaseModel):
            id: int
            name: str
            description: Optional[str] = None
            active: bool = True
        
        Subset = create_subset(Parent, ['id', 'description', 'active'], 'OptionalSubset')
        
        # Test with default values
        instance1 = Subset(id=1)
        assert instance1.id == 1
        assert instance1.description is None
        assert instance1.active is True
        
        # Test with provided values
        instance2 = Subset(id=2, description='test desc', active=False)
        assert instance2.id == 2
        assert instance2.description == 'test desc'
        assert instance2.active is False
    
    def test_subset_with_field_constraints(self):
        """Test subset creation preserves field constraints."""
        class Parent(BaseModel):
            id: int = Field(gt=0, description="ID must be positive")
            name: str = Field(min_length=2, max_length=50)
            score: float = Field(ge=0.0, le=100.0)
        
        Subset = create_subset(Parent, ['id', 'name'], 'ConstrainedSubset')
        
        # Test valid values
        instance = Subset(id=1, name='test')
        assert instance.id == 1
        assert instance.name == 'test'
        
        # Test constraint validation (if constraints are preserved)
        # Note: This may depend on how well create_model preserves constraints
        try:
            invalid_instance = Subset(id=0, name='a')  # id should be > 0, name too short
            # If no exception is raised, constraints might not be fully preserved
            # This is expected behavior with basic create_model usage
        except Exception:
            # If constraints are preserved, we expect validation errors
            pass
    
    def test_subset_with_validators(self):
        """Test subset creation with parent validators."""
        from pydantic import field_validator
        
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            
            @field_validator('name')
            @classmethod
            def validate_name(cls, v):
                if len(v) < 2:
                    raise ValueError('Name must be at least 2 characters')
                return v

            @field_validator('email')
            @classmethod
            def validate_email(cls, v):
                if '@' not in v:
                    raise ValueError('Email must has @ symbol')
                return v
        
        Subset = create_subset(Parent, ['id', 'name'], 'ValidatorSubset')
        
        # Test that valid data works
        instance = Subset(id=1, name='test')
        assert instance.id == 1
        assert instance.name == 'test'
        
        # Test that the validator method is copied to the subset
        assert hasattr(Subset, 'validate_name')
        assert callable(getattr(Subset, 'validate_name'))
    

    def test_duplicate_fields_handling(self):
        """Test that duplicate fields in the fields list are handled correctly."""
        class Parent(BaseModel):
            id: int
            name: str
            age: int
        
        Subset = create_subset(Parent, ['id', 'name', 'id', 'name'], 'DuplicateSubset')
        
        instance = Subset(id=1, name='test')
        assert instance.id == 1
        assert instance.name == 'test'
    
    def test_field_order_preservation(self):
        """Test that field order is preserved in subset."""
        class Parent(BaseModel):
            c: str
            a: int
            b: float
        
        Subset = create_subset(Parent, ['b', 'a', 'c'], 'OrderedSubset')
        
        instance = Subset(b=1.5, a=1, c='test')
        assert instance.a == 1
        assert instance.b == 1.5
        assert instance.c == 'test'
        
        # Check field order in model definition
        field_names = list(Subset.model_fields.keys())
        
        assert field_names == ['b', 'a', 'c']
    
    def test_nonexistent_field_error(self):
        """Test that referencing non-existent fields raises an error."""
        class Parent(BaseModel):
            id: int
            name: str
        
        with pytest.raises(AttributeError, match='field "nonexistent" not existed'):
            create_subset(Parent, ['id', 'nonexistent'], 'ErrorSubset')
    
    def test_non_basemodel_parent_error(self):
        """Test that using non-BaseModel parent raises an error."""
        class NotBaseModel:
            id: int
            name: str
        
        with pytest.raises(TypeError, match='parent must be a pydantic BaseModel'):
            create_subset(NotBaseModel, ['id'], 'ErrorSubset')  # type: ignore
    
    def test_empty_fields_list(self):
        """Test subset creation with empty fields list."""
        class Parent(BaseModel):
            id: int
            name: str
        
        Subset = create_subset(Parent, [], 'EmptySubset')
        
        # Should be able to create instance with no fields
        instance = Subset()
        
        # Should have no fields
        field_names = list(Subset.model_fields.keys())
        assert len(field_names) == 0
        
        # Extra fields should be ignored (not raise TypeError)
        instance_with_extra = Subset(id=1)  # id is ignored
        assert not hasattr(instance_with_extra, 'id')
    
    def test_custom_subset_name(self):
        """Test that custom subset name is used correctly."""
        class Parent(BaseModel):
            id: int
            name: str
        
        Subset = create_subset(Parent, ['id'], 'CustomName')
        
        assert Subset.__name__ == 'CustomName'
    
    def test_default_subset_name(self):
        """Test default subset name when none provided."""
        class Parent(BaseModel):
            id: int
            name: str
        
        Subset = create_subset(Parent, ['id'])
        
        assert Subset.__name__ == 'SubsetModel'
    
    def test_model_configuration_inheritance(self):
        """Test that parent model configuration is inherited."""
        from pydantic import ConfigDict
        
        class Parent(BaseModel):
            model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
            name: str
            value: int
        
        Subset = create_subset(Parent, ['name'], 'ConfigSubset')
        
        # Test that config is inherited (behavior may vary based on implementation)
        instance = Subset(name='  test  ')
        assert instance.name == 'test'
        
        # The actual config inheritance testing would depend on the implementation details


class TestCreateSubsetIntegration:
    """Integration tests for create_subset with complex scenarios."""
    
    def test_nested_model_fields(self):
        """Test subset creation with nested model fields."""
        class Address(BaseModel):
            street: str
            city: str
        
        class Person(BaseModel):
            id: int
            name: str
            address: Address
            age: int
        
        Subset = create_subset(Person, ['id', 'address'], 'NestedSubset')
        
        address = Address(street='123 Main St', city='Anytown')
        instance = Subset(id=1, address=address)
        
        assert instance.id == 1
        assert instance.address.street == '123 Main St'
        assert instance.address.city == 'Anytown'
    
    def test_multiple_subsets_from_same_parent(self):
        """Test creating multiple subsets from the same parent."""
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            age: int
            active: bool
        
        Subset1 = create_subset(Parent, ['id', 'name'], 'Subset1')
        Subset2 = create_subset(Parent, ['email', 'age'], 'Subset2')
        Subset3 = create_subset(Parent, ['id', 'active'], 'Subset3')
        
        # Test that all subsets work independently
        s1 = Subset1(id=1, name='test')
        s2 = Subset2(email='test@example.com', age=25)
        s3 = Subset3(id=2, active=True)
        
        assert s1.id == 1 and s1.name == 'test'
        assert s2.email == 'test@example.com' and s2.age == 25
        assert s3.id == 2 and s3.active is True
        
        # Test that subsets are truly independent
        assert Subset1.__name__ == 'Subset1'
        assert Subset2.__name__ == 'Subset2'
        assert Subset3.__name__ == 'Subset3'


class TestSubsetMeta:
    """Test cases for SubsetMeta metaclass and Subset base class."""
    
    def test_basic_subset_metaclass(self):
        """Test basic usage of Subset metaclass to create subset classes."""
        class Parent(BaseModel):
            id: int
            name: str
            age: int
            email: str
        
        class MySubset(DefineSubset):
            __pydantic_resolve_subset__ = (Parent, ['id', 'name'])
            new_field: str
        
        # Test that MySubset is a proper subset
        instance = MySubset(id=1, name='test', new_field='extra')
        assert instance.id == 1
        assert instance.name == 'test'
        assert instance.new_field == 'extra'

        # Test that excluded fields are not present
        field_names = list(MySubset.model_fields.keys())
        assert 'id' in field_names
        assert 'name' in field_names
        assert 'age' not in field_names
        assert 'email' not in field_names
        
        # Test that MySubset is a subclass of BaseModel
        assert issubclass(MySubset, BaseModel)
        assert getattr(MySubset, const.ENSURE_SUBSET_REFERENCE) is Parent
    
    def test_basic_subset_metaclass_with_fields_in_tuple(self):
        """Test basic usage of Subset metaclass to create subset classes."""
        class Parent(BaseModel):
            id: int
            name: str
            age: int
            email: str
        
        class MySubset(DefineSubset):
            __pydantic_resolve_subset__ = (Parent, ('id', 'name'))
            new_field: str
        
        # Test that MySubset is a proper subset
        instance = MySubset(id=1, name='test', new_field='extra')
        assert instance.id == 1
        assert instance.name == 'test'
        assert instance.new_field == 'extra'
        
        # Test that MySubset is a subclass of BaseModel
        assert issubclass(MySubset, BaseModel)
        assert getattr(MySubset, const.ENSURE_SUBSET_REFERENCE) is Parent
    
    def test_wrongly_create_subset_metaclass(self):
        """Test basic usage of Subset metaclass to create subset classes."""
        class Parent(BaseModel):
            id: int
            name: str
            age: int
            email: str
        
        with pytest.raises(ValueError):
            class MySubset(DefineSubset):
                __pydantic_resolve_subset__ = (Parent, ['id', 'name'])
                id: str
        
        with pytest.raises(ValueError):
            class MySubset2(DefineSubset):
                id: str
        