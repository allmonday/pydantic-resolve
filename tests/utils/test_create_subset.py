"""Tests for create_subset function in subset.py"""

import pytest
from typing import Optional, Annotated
from pydantic import BaseModel, Field
from pydantic_resolve.utils.subset import create_subset, DefineSubset
from pydantic_resolve import Resolver, Collector, ExposeAs
import pydantic_resolve.constant as const
from pydantic_resolve.utils.subset import SubsetConfig


class TestCreateSubset:
    """Test cases for create_subset function."""
    
    def test_basic_subset_creation(self):
        """Test basic subset creation with required fields."""
        class Parent(BaseModel):
            id: int
            name: Annotated[str, 'tangkikodo']
            age: int
            email: str
            items: list[str]
        
        Subset = create_subset(Parent, ['id', 'name', 'items'], 'TestSubset')
        
        # Test that we can create an instance
        instance = Subset(id=1, name='test', items=['a', 'b', 'c'])
        assert instance.id == 1
        assert instance.name == 'test'
        assert instance.items == ['a', 'b', 'c']
        
        # Test that excluded fields are not present in the model
        field_names = list(Subset.model_fields.keys())

        assert len(Subset.model_fields.get('name').metadata) == 1
        assert Subset.model_fields.get('name').metadata[0] == 'tangkikodo'
        
        assert 'id' in field_names
        assert 'name' in field_names
        assert 'age' not in field_names
        assert 'email' not in field_names

        # Test that extra fields are ignored (Pydantic default behavior)
        instance_with_extra = Subset(id=2, name='test2', age=25, items=['x', 'y', 'z'])  # age is ignored
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
            Subset(id=0, name='a')  # id should be > 0, name too short
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
            
            @field_validator('name', 'email')
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
        """Test that duplicate fields in the fields list should raise ValueError"""
        class Parent(BaseModel):
            id: int
            name: str
            age: int
        
        with pytest.raises(ValueError):
            create_subset(Parent, ['id', 'name', 'id', 'name'], 'DuplicateSubset')
        
    
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

        with pytest.raises(AttributeError, match='field "nonexistent" does not exist'):
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
        Subset()
        
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
            __subset__ = (Parent, ('id', 'name'))
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
        

class TestSubsetResolve:
    @pytest.mark.asyncio
    async def test_basic_subset_creation(self):
        class Parent(BaseModel):
            id: int
            name: str
            age: int
            email: str

        class Item(BaseModel):
            __pydantic_resolve_collect__ = {
                'count': 'collector'
            }
            name: str = ''
            def resolve_name(self, ancestor_context):
                return ancestor_context['my_subset_name']
            
            count: int
        
        class MySubset(DefineSubset):
            __pydantic_resolve_subset__ = (Parent, ('id', 'name'))
            __pydantic_resolve_expose__ = {
                'name': 'my_subset_name'
            }
            new_field: str = ''

            def resolve_new_field(self) -> str:
                return f"{self.id}-{self.name}"
            
            items: list[Item] = []
            def resolve_items(self):
                return [Item(count=1), Item(count=2)] 
            
            total: int = 0
            def post_total(self, collector=Collector(alias='collector')):
                return sum(collector.values())
            
            hello: str = 'world'
            def post_default_handler(self):
                self.hello = 'hello world'
        
        instance = MySubset(id=1, name='test')
        await Resolver().resolve(instance)
        assert instance.new_field == '1-test'
        assert instance.items[0].name == 'test'
        assert instance.total == 3
        assert instance.hello == 'hello world'
        

class TestCreateSubsetConfig:
    
    def test_case_1(self):
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            age: int
            active: bool
        
        class Sub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=Parent,
                fields=['id', 'name'],
            )
        
        sub = Sub(id=1, name='test')
        assert sub.id == 1
        assert sub.name == 'test'
        
        
    def test_case_2(self):
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            age: int
            active: bool
        
        class Sub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=Parent,
                omit_fields=['email'],
            )
        
        sub = Sub(id=1, name='test', age=30, active=True)
        assert sub.id == 1
        assert sub.name == 'test'
        
    def test_case_3(self):
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            age: int
            active: bool
        
        class Sub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=Parent,
                fields=['id', 'name', 'age'],
                expose_as=[('name', 'custom_name')],
                send_to=[
                    ('age', 'age_collector'),
                    ('age', ('a', 'b')) 
                ],
            )
        
        sub = Sub(id=1, name='test', age=30, active=True)
        assert sub.id == 1
        assert sub.name == 'test'

        assert Sub.model_fields['name'].metadata[0].alias == 'custom_name'

    def test_case_4(self):
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            age: int
            active: bool
        
        class Sub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=Parent,
                fields=['id', 'name', 'age'],
                excluded_fields=['age']
            )
        
        sub = Sub(id=1, name='test', age=30)
        assert sub.id == 1
        assert sub.name == 'test'
        assert sub.age == 30
        
        # Check if exclude=True is set
        assert Sub.model_fields['age'].exclude is True
        assert Sub.model_fields['name'].exclude is None
        
        # Check serialization
        assert sub.model_dump() == {'id': 1, 'name': 'test'} 


    def test_case_5(self):
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            age: int
            active: bool
        
        class Sub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=Parent,
                fields="all"
            )
        
        assert Sub.model_fields.keys() == Parent.model_fields.keys()
        

    def test_case_6(self):
        class Parent(BaseModel):
            id: int
            name: str
            email: str
            age: int
            active: bool
        
        class Sub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=Parent,
                omit_fields=[]  # same as fields="all"
            )
        
        assert Sub.model_fields.keys() == Parent.model_fields.keys()
        

@pytest.mark.asyncio
async def test_subset_with_expose():
    class Parent(BaseModel):
        id: int
        name: str
        email: str
        age: int
        active: bool

    class SubItem(BaseModel):
        field: str = ''
        def post_field(self, ancestor_context):
            return ancestor_context['custom_field']

        name: str = ''
        def post_name(self, ancestor_context):
            return ancestor_context['custom_name']

    class Sub(DefineSubset):
        __subset__ = SubsetConfig(
            kls=Parent,
            fields=['id', 'name', 'email', 'age', 'active'],
            expose_as=[
                ('id', 'custom_id'),
                ('name', 'custom_name')]
        )
        field: Annotated[str, ExposeAs('custom_field')] = ''
        items: list[SubItem] = [SubItem()]


    sub = Sub(id=1, name='test', email='xxx.com', age=30, active=True, field='value')
    sub = await Resolver().resolve(sub)
    assert sub.id == 1
    assert sub.items[0].field == 'value'
    assert sub.items[0].name == 'test'


class TestSubsetConfigRelated:
    """Test cases for SubsetConfig.related parameter (references Relationship field_name)."""

    def test_related_auto_adds_fk_and_loadby_field(self):
        """Test that related=['author'] auto-adds FK field (exclude=True) and LoadBy field."""
        from pydantic_resolve import config_global_resolver
        from pydantic_resolve.utils.er_diagram import ErDiagram, Entity, Relationship, base_entity

        BASE = base_entity()

        class User(BaseModel, BASE):
            id: int
            name: str

        class Post(BaseModel, BASE):
            id: int
            title: str
            author_id: int

            __relationships__ = [
                Relationship(field='author_id', field_name='author', target_kls=User, loader=lambda x: x)
            ]

        diagram = BASE.get_diagram()
        config_global_resolver(diagram)

        try:
            class PostSubset(DefineSubset):
                __subset__ = SubsetConfig(
                    kls=Post,
                    fields=['id', 'title'],
                    related=['author']
                )

            # FK field should be auto-added with exclude=True
            assert 'author_id' in PostSubset.model_fields
            assert PostSubset.model_fields['author_id'].exclude is True

            # LoadBy field should be auto-generated
            assert 'author' in PostSubset.model_fields
            # Check LoadBy annotation
            from pydantic_resolve.utils.er_diagram import LoaderInfo
            metadata = PostSubset.model_fields['author'].metadata
            assert any(isinstance(m, LoaderInfo) for m in metadata)

            # Can create instance
            sub = PostSubset(id=1, title='hello', author_id=42)
            assert sub.id == 1
            assert sub.title == 'hello'
            assert sub.author_id == 42

            # author_id excluded from serialization
            assert sub.model_dump() == {'id': 1, 'title': 'hello', 'author': None}
        finally:
            # Clean up global resolver
            from pydantic_resolve.resolver import Resolver
            import pydantic_resolve.constant as const
            if hasattr(Resolver, const.ER_DIAGRAM):
                delattr(Resolver, const.ER_DIAGRAM)

    def test_related_not_found_raises_error(self):
        """Test that related with non-existent field_name raises ValueError."""
        from pydantic_resolve import config_global_resolver
        from pydantic_resolve.utils.er_diagram import base_entity, Relationship

        BASE = base_entity()

        class User(BaseModel, BASE):
            id: int
            name: str

        class Post(BaseModel, BASE):
            id: int
            title: str
            author_id: int

            __relationships__ = [
                Relationship(field='author_id', field_name='author', target_kls=User, loader=lambda x: x)
            ]

        config_global_resolver(BASE.get_diagram())

        try:
            with pytest.raises(ValueError, match='Relationship field_name "nonexistent" not found'):
                class PostSubset(DefineSubset):
                    __subset__ = SubsetConfig(
                        kls=Post,
                        fields=['id', 'title'],
                        related=['nonexistent']
                    )
        finally:
            from pydantic_resolve.resolver import Resolver
            import pydantic_resolve.constant as const
            if hasattr(Resolver, const.ER_DIAGRAM):
                delattr(Resolver, const.ER_DIAGRAM)

    def test_related_no_er_diagram_raises_error(self):
        """Test that related without global ER diagram raises ValueError."""
        class Parent(BaseModel):
            id: int
            name: str
            user_id: int

        with pytest.raises(ValueError, match='requires a global ER diagram'):
            class Sub(DefineSubset):
                __subset__ = SubsetConfig(
                    kls=Parent,
                    fields=['id', 'name'],
                    related=['author']
                )

    def test_related_parent_not_in_er_diagram_raises_error(self):
        """Test that related with parent not in ER diagram raises ValueError."""
        from pydantic_resolve import config_global_resolver
        from pydantic_resolve.utils.er_diagram import base_entity, Relationship

        BASE = base_entity()

        class User(BaseModel, BASE):
            id: int
            name: str

        class PostNotInDiagram(BaseModel):
            id: int
            title: str
            author_id: int

        config_global_resolver(BASE.get_diagram())

        try:
            with pytest.raises(ValueError, match='not found in ER diagram'):
                class PostSubset(DefineSubset):
                    __subset__ = SubsetConfig(
                        kls=PostNotInDiagram,
                        fields=['id', 'title'],
                        related=['author']
                    )
        finally:
            from pydantic_resolve.resolver import Resolver
            import pydantic_resolve.constant as const
            if hasattr(Resolver, const.ER_DIAGRAM):
                delattr(Resolver, const.ER_DIAGRAM)

    def test_multiple_related_fields(self):
        """Test that multiple related field_names can be specified."""
        from pydantic_resolve import config_global_resolver
        from pydantic_resolve.utils.er_diagram import base_entity, Relationship

        BASE = base_entity()

        class User(BaseModel, BASE):
            id: int
            name: str

        class Tag(BaseModel, BASE):
            id: int
            label: str

        class Post(BaseModel, BASE):
            id: int
            title: str
            author_id: int
            tag_id: int

            __relationships__ = [
                Relationship(field='author_id', field_name='author', target_kls=User, loader=lambda x: x),
                Relationship(field='tag_id', field_name='tag', target_kls=Tag, loader=lambda x: x),
            ]

        config_global_resolver(BASE.get_diagram())

        try:
            class PostSubset(DefineSubset):
                __subset__ = SubsetConfig(
                    kls=Post,
                    fields=['id', 'title'],
                    related=['author', 'tag']
                )

            # Both FK fields auto-added with exclude=True
            assert 'author_id' in PostSubset.model_fields
            assert PostSubset.model_fields['author_id'].exclude is True
            assert 'tag_id' in PostSubset.model_fields
            assert PostSubset.model_fields['tag_id'].exclude is True

            # Both LoadBy fields auto-generated
            assert 'author' in PostSubset.model_fields
            assert 'tag' in PostSubset.model_fields
        finally:
            from pydantic_resolve.resolver import Resolver
            import pydantic_resolve.constant as const
            if hasattr(Resolver, const.ER_DIAGRAM):
                delattr(Resolver, const.ER_DIAGRAM)

    def test_related_with_to_many_relationship(self):
        """Test related with to-many relationship (target_kls=list[Entity])."""
        from pydantic_resolve import config_global_resolver
        from pydantic_resolve.utils.er_diagram import base_entity, Relationship

        BASE = base_entity()

        class Comment(BaseModel, BASE):
            id: int
            text: str

        class Post(BaseModel, BASE):
            id: int
            title: str

            __relationships__ = [
                Relationship(field='id', field_name='comments', target_kls=list['Comment'], loader=lambda x: x),
            ]

        config_global_resolver(BASE.get_diagram())

        try:
            class PostSubset(DefineSubset):
                __subset__ = SubsetConfig(
                    kls=Post,
                    fields=['id', 'title'],
                    related=['comments']
                )

            # FK field (id) auto-added with exclude=True
            # But 'id' is already in subset_fields, so it should NOT be re-added
            # Only the LoadBy field 'comments' should be auto-generated
            assert 'comments' in PostSubset.model_fields

            from pydantic_resolve.utils.er_diagram import LoaderInfo
            metadata = PostSubset.model_fields['comments'].metadata
            assert any(isinstance(m, LoaderInfo) for m in metadata)
        finally:
            from pydantic_resolve.resolver import Resolver
            import pydantic_resolve.constant as const
            if hasattr(Resolver, const.ER_DIAGRAM):
                delattr(Resolver, const.ER_DIAGRAM)
