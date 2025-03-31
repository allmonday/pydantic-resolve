from typing import List, Optional
import pytest
from pydantic import BaseModel, ValidationError
from pydantic_resolve import Resolver

@pytest.mark.asyncio
async def test_1():
    class Base(BaseModel):
        name: str
        id: int

    class Child(BaseModel):
        name: str
    
    class Container(BaseModel):
        items: List[Child] = []
        def resolve_items(self):
            return [Base(name='name-1', id=1), Base(name='name-2', id=2)]

    c = Container()
    with pytest.raises(ValidationError):
        c = await Resolver().resolve(c)

    c = await Resolver(enable_from_attribute_in_type_adapter=True).resolve(c)
    assert c.items[0].name == 'name-1'


@pytest.mark.asyncio
async def test_2():
    class Child(BaseModel):
        name: str
    
    class Container(BaseModel):
        items: List[Child] = []
        def resolve_items(self):
            return [dict(name='name-1', id=1), dict(name='name-2', id=2)]

    c = Container()
    c = await Resolver().resolve(c)

    assert c.items[0].name == 'name-1'


@pytest.mark.asyncio
async def test_3():
    class Child(BaseModel):
        name: str
    
    class Container(BaseModel):
        item: Optional[Child] = None
        def resolve_item(self):
            return dict(name='name-1', id=1)

    c = Container()
    c = await Resolver().resolve(c)

    assert c.item and c.item.name == 'name-1'

