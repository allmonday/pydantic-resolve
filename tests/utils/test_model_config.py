from pydantic_resolve.utils.openapi import model_config
from pydantic import BaseModel, Field, TypeAdapter
from pydantic_resolve import Resolver
from pydantic.json_schema import GenerateJsonSchema as GenerateJsonSchema
import pytest

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
async def test_schema_config_required():
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
async def test_raw_schema_in_serialization():
    """
    in pydantic v2 and fastapi, it will generate json schema in mode: serialization
    so that you can remove model_config decorator.
    """
    class Y(BaseModel):
        name: str
        id: int = 0
        password: str = Field(default='', exclude=True)

    schema = Y.model_json_schema(mode='serialization')
    assert list((schema['properties']).keys()) == ['name', 'id']
    assert set(schema['required']) == {'name'}
