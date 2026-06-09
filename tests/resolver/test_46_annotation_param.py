from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest

class A(BaseModel):
    id: int
    name: str

    desc: str = ''
    def post_desc(self):
        return f'a: {self.name}-{self.id}'


class B(BaseModel):
    id: int
    name: str

    desc: str = ''
    def post_desc(self):
        return f'b: {self.name}-{self.id}'


Item = A | B

@pytest.mark.asyncio
async def test_annotation_param():
    items: list[Item] = [
        A(id=1, name='item1'),
        B(id=2, name='item2'),
        A(id=3, name='item3'),
    ]

    resolved_items = await Resolver(annotation=Item).resolve(items)

    assert resolved_items[0].desc == 'a: item1-1'
    assert resolved_items[1].desc == 'b: item2-2'
    assert resolved_items[2].desc == 'a: item3-3'

@pytest.mark.asyncio
async def test_without_annotation_param():
    """Without annotation, Resolver deduces root_class from the first element.
    In BFS mode only the first element's class is scanned, so B's post_desc
    is silently skipped (no error, but desc remains empty for B instances)."""
    items: list[Item] = [
        A(id=1, name='item1'),
        B(id=2, name='item2'),
        A(id=3, name='item3'),
    ]
    resolved = await Resolver().resolve(items)
    assert resolved[0].desc == 'a: item1-1'
    assert resolved[1].desc == ''  # B was not scanned, post_desc never ran
    assert resolved[2].desc == 'a: item3-3'