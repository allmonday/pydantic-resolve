from pydantic import BaseModel
from pydantic_resolve import Resolver
import pytest
from typing import Optional


# fix bug: 
# from v1.11.2 post method will continue resolve the field, which will lost the ancestor context
# because the ancestor is parallel to the field, so the ancestor context will not be passed to the field
# so the decision is disallow the post method to resolve the field

class Item(BaseModel):
    name: str
    game_name: str = ''
    def resolve_game_name(self, ancestor_context):
        return ancestor_context['game_name']

class Game(BaseModel):
    __pydantic_resolve_expose__ = {
        'name': 'game_name'
    }
    name: str

    item: list[Item] = []
    def resolve_item(self):
        return [Item(name='item1')]

class Container(BaseModel):
    game: Optional[Game] = None

    game_item: list[Item] = []
    def post_game_item(self):
        return self.game.item

@pytest.mark.asyncio
async def test_expose_not_found():
    game = Container(game=Game(name='game1'))
    game = await Resolver().resolve(game)
    assert game.dict() == {
        'game': {
            'name': 'game1',
            'item': [{'name': 'item1','game_name': 'game1'}]
        },
        'game_item': [{'name': 'item1','game_name': 'game1'}],
    }