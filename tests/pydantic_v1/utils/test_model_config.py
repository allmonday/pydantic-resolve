from pydantic_resolve.util import model_config
from pydantic import BaseModel, Field
from pydantic_resolve import Resolver, LoaderDepend as LD, ensure_subset
import pytest
import json
from typing import List

@pytest.mark.asyncio
async def test_schema_config_hidden():

    class X(BaseModel):
        id: int = 0
        name: str
    
    async def loader_fn(keys):
        return keys

    @model_config()
    @ensure_subset(X)
    class Y(BaseModel):
        id: int = Field(0, exclude=True)
        name: str

        password: str = Field('', exclude=True)
        def resolve_password(self, loader=LD(loader_fn)):
            return loader.load('xxx')
            
        passwords: List[str] = Field(default_factory=list, exclude=True)
        def resolve_passwords(self):
            return ['a', 'b']

    schema = Y.schema()
    assert list((schema['properties']).keys()) == ['name']

    y = Y(name='kikodo')
    assert y.dict() == {'name': 'kikodo'}
    assert y.json() == json.dumps({'name': 'kikodo'})

    y = await Resolver().resolve(y) 
    assert y.dict() == {'name': 'kikodo'}
    assert y.json() == json.dumps({'name': 'kikodo'})


@pytest.mark.asyncio
async def test_schema_config_hidden_with_field():
    """Field(exclude=True) will also work """

    @model_config()
    class Y(BaseModel):
        id: int = Field(0, exclude=True)
        def resolve_id(self):
            return 1

        name: str = Field(exclude=True)

        password: str = Field('', exclude=True)
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

@pytest.mark.asyncio
async def test_nested_loader():

    async def load_items(keys):
        return [[dict(name=f'item-{key}-{idx}') for idx in range(1)] for key in keys]

    async def load_details(keys):
        return [['1', '2'] for key in keys]

    @model_config()
    class Item(BaseModel):
        name: str
        details: List[str] = Field(default_factory=list, exclude=True)
        def resolve_details(self, loader=LD(load_details)):
            return loader.load(self.name)

    @model_config()
    class Record(BaseModel):
        id: int = Field(0, exclude=True)
        items: List[Item] = []
        def resolve_items(self, loader=LD(load_items)):
            return loader.load(self.id)

    record = Record()
    record = await Resolver().resolve(record)
    assert record.dict() == {'items': [{'name': 'item-0-0'}]}

    schema = Record.schema()
    assert schema['required'] == ['items']
    assert set(schema['properties'].keys()) == {'items'}
    assert set(schema['definitions']['Item']['properties'].keys()) == {'name'}