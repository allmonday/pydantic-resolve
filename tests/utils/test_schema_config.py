from pydantic_resolve.util import schema_config
from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest

@pytest.mark.asyncio
async def test_schema_config():

    @schema_config(hidden_fields=['id', 'password2'], default_required=True)
    class Y(BaseModel):
        id: int = 0
        def resolve_id(self):
            return 1

        name: str

        password2: str = ''
        def resolve_password2(self):
            return 'confidential'

    schema = Y.schema()
    assert list((schema['properties']).keys()) == ['name']

    y = Y(name='kikodo')

    y = await Resolver().resolve(y) 
    assert y.dict() == {'name': 'kikodo'}


@pytest.mark.asyncio
async def test_schema_config_required():
    @schema_config(hidden_fields=['password2'])
    class Y(BaseModel):
        id: int = 0
        def resolve_id(self):
            return 1

        name: str

        password2: str = ''
        def resolve_password2(self):
            return 'confidential'

    schema = Y.schema()
    assert set(schema['required']) == {'id', 'name'}


@pytest.mark.asyncio
async def test_schema_config_required_false():
    @schema_config(default_required=False)
    class Y(BaseModel):
        id: int = 0
        def resolve_id(self):
            return 1

        name: str

        password2: str = ''
        def resolve_password2(self):
            return 'confidential'

    schema = Y.schema()
    assert set(schema['required']) == {'name'}
