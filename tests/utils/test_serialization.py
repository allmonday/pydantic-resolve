from pydantic import BaseModel, Field
from pydantic_resolve import serialization
from typing import List, Optional, Annotated


# ============ Test 1: Single level nesting ============
class Address(BaseModel):
    street: str = ''
    city: str = ''


@serialization
class Person(BaseModel):
    name: str = ''
    address: Annotated[Address | None, 'hello'] = None


def test_single_level_nesting():
    """Test that serialization decorator works with single level nesting"""
    schema = Person.model_json_schema(mode='serialization')

    # Root class: name is required, address is a nested model
    assert 'name' in schema['required']
    assert 'address' in schema['properties']

    # Nested class: both street and city should be required
    address_def = schema['$defs']['Address']
    assert 'street' in address_def['required']
    assert 'city' in address_def['required']


# ============ Test 2: Multi-level nesting ============
class Country(BaseModel):
    name: str
    code: str


class City(BaseModel):
    name: str
    country: Optional[Country] = None


@serialization
class User(BaseModel):
    name: str
    city: City


def test_multi_level_nesting():
    """Test that serialization decorator works with multi-level nesting (3 levels)"""
    schema = User.model_json_schema(mode='serialization')

    # Level 1: User
    assert 'name' in schema['required']

    # Level 2: City
    city_def = schema['$defs']['City']
    assert 'name' in city_def['required']
    assert 'country' in city_def['properties']

    # Level 3: Country
    country_def = schema['$defs']['Country']
    assert 'name' in country_def['required']
    assert 'code' in country_def['required']


# ============ Test 3: List nesting ============
class Item(BaseModel):
    id: int
    name: str


@serialization
class Order(BaseModel):
    items: List[Item]
    total: int


def test_list_nesting():
    """Test that serialization decorator works with List[Model] nesting"""
    schema = Order.model_json_schema(mode='serialization')

    # Root class: items and total are required
    assert 'items' in schema['required']
    assert 'total' in schema['required']

    # Nested class in list: Item should have required fields
    item_def = schema['$defs']['Item']
    assert 'id' in item_def['required']
    assert 'name' in item_def['required']


# ============ Test 4: Exclude recursion ============
class InnerWithExclude(BaseModel):
    visible: str
    hidden: str = Field(default='', exclude=True)

    def resolve_hidden(self):
        return 'hidden_value'


@serialization
class OuterWithExclude(BaseModel):
    name: str
    inner: InnerWithExclude


def test_exclude_recursion():
    """Test that exclude fields in nested models are also excluded"""
    schema = OuterWithExclude.model_json_schema(mode='serialization')

    # Root class
    assert 'name' in schema['required']

    # Nested class: hidden should be excluded from properties
    inner_def = schema['$defs']['InnerWithExclude']
    assert 'visible' in inner_def['properties']
    assert 'hidden' not in inner_def['properties']


# ============ Test 5: Mixed scenario ============
class Tag(BaseModel):
    id: int
    label: str


class Config(BaseModel):
    enabled: bool = True
    debug: str = Field(default='', exclude=True)

    def resolve_debug(self):
        return 'debug_value'


@serialization
class Product(BaseModel):
    name: str
    price: int
    tags: List[Tag]
    config: Optional[Config] = None


def test_mixed_scenario():
    """Test mixed scenario: nested + List + optional + exclude"""
    schema = Product.model_json_schema(mode='serialization')

    # Root class
    assert 'name' in schema['required']
    assert 'price' in schema['required']
    assert 'tags' in schema['required']

    # List nested: Tag
    tag_def = schema['$defs']['Tag']
    assert 'id' in tag_def['required']
    assert 'label' in tag_def['required']

    # Optional nested: Config
    config_def = schema['$defs']['Config']
    assert 'enabled' in config_def['properties']
    assert 'debug' not in config_def['properties']  # excluded
