from pydantic_resolve.utils.openapi import model_config
from pydantic import BaseModel, Field
from pydantic_resolve import Resolver
from pydantic.json_schema import GenerateJsonSchema as GenerateJsonSchema
import pytest
from typing import Annotated

@pytest.mark.asyncio
async def test_schema_config():

    @model_config()
    class Y(BaseModel):
        id: int = Field(default=0, exclude=True)
        def resolve_id(self):
            return 1

        name: str

        password: str = Field(default='', exclude=True)
        def resolve_password(self):
            return 'confidential'

    schema = Y.model_json_schema()
    assert list((schema['properties']).keys()) == ['name']

    y = Y(name='kikodo')

    y = await Resolver().resolve(y) 
    assert y.model_dump() == {'name': 'kikodo'}



@pytest.mark.asyncio
async def test_schema_config_required_false():
    @model_config(default_required=False)
    class Y(BaseModel):
        id: int = 0
        def resolve_id(self):
            return 1

        name: str

        password: str = ''
        def resolve_password(self):
            return 'confidential'

    schema = Y.model_json_schema()
    assert set(schema['required']) == {'name'}


@pytest.mark.asyncio
async def test_schema_config_required_true():
    @model_config(default_required=True)
    class Y(BaseModel):
        id: Annotated[int, 'hello'] = 0

        name: str

        password: str = ''
        def resolve_password(self):
            return 'confidential'

    schema = Y.model_json_schema()
    assert set(schema['required']) == {'name', 'id', 'password'}


@pytest.mark.asyncio
async def test_raw_schema_in_serialization():
    """
    in pydantic v2 and fastapi, it will generate json schema in mode: serialization
    it will ignore fields with exclude=True, but model_config still helps to set required fields
    """
    class Y(BaseModel):
        name: str
        id: int = 0
        password: str = Field(default='', exclude=True)

    schema = Y.model_json_schema(mode='serialization')
    assert list((schema['properties']).keys()) == ['name', 'id']
    assert set(schema['required']) == {'name'}


@pytest.mark.asyncio
async def test_schema_config_inheritance_issue():
    """
    Test that demonstrates kls.model_fields misses child class fields.
    This test will fail if the code uses kls.model_fields instead of model.model_fields
    """
    @model_config()
    class Base(BaseModel):
        id: int = 0
        name: str

    # Child class inherits and adds new fields
    class Child(Base):
        age: int = 0
        email: str = ''

    schema = Child.model_json_schema()

    # Using model.model_fields (current implementation) correctly includes all fields
    # If using kls.model_fields, it would miss 'age' and 'email'
    assert set(schema['required']) == {'name', 'id', 'age', 'email'}

    # Verify properties also include all fields
    assert set(schema['properties'].keys()) == {'name', 'id', 'age', 'email'}
