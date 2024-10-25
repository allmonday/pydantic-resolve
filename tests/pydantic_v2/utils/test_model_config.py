from pydantic_resolve.util import model_config
from pydantic import BaseModel, Field
from pydantic_resolve import Resolver
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

