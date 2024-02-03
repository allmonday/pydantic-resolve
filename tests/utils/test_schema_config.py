from pydantic_resolve.util import model_config
from pydantic import BaseModel, Field
from pydantic_resolve import Resolver
import pytest

@pytest.mark.asyncio
async def test_schema_config_hidden():

    @model_config(hidden_fields=['id', 'password'])
    class Y(BaseModel):
        id: int = 0
        def resolve_id(self):
            return 1

        name: str

        password: str = ''
        def resolve_password(self):
            return 'confidential'

    schema = Y.schema()
    assert list((schema['properties']).keys()) == ['name']

    y = Y(name='kikodo')

    y = await Resolver().resolve(y) 
    assert y.dict() == {'name': 'kikodo'}


@pytest.mark.asyncio
async def test_schema_config_hidden_with_field():
    """Field(exclude=True) will also work """

    @model_config(hidden_fields=['id', 'password'])
    class Y(BaseModel):
        id: int = 0
        def resolve_id(self):
            return 1

        name: str = Field(exclude=True)

        password: str = ''
        def resolve_password(self):
            return 'confidential'

    schema = Y.schema()
    assert list((schema['properties']).keys()) == []

    y = Y(name='kikodo')

    y = await Resolver().resolve(y) 
    assert y.dict() == {}



@pytest.mark.asyncio
async def test_schema_config_required():
    @model_config()
    class Y(BaseModel):
        id: int = 0
        def resolve_id(self):
            return 1

        name: str

        password: str = ''
        def resolve_password(self):
            return 'confidential'

    schema = Y.schema()
    assert set(schema['required']) == {'id', 'name', 'password'}


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

    schema = Y.schema()
    assert set(schema['required']) == {'name'}
