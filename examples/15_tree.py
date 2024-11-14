from __future__ import annotations
from pydantic import BaseModel
from pydantic_resolve import Resolver
from typing import List
import asyncio

class Tag(BaseModel):
    name: str

    full_path: str = ''
    def resolve_full_path(self, parent):
        if parent:
            return f'{parent.full_path}/{self.name}'
        else:
            return self.name

    children: List[Tag] = []


tag_data = dict(name='root', children=[
        dict(name='a', children=[
            dict(name='b', children=[
                dict(name='e', chidrent=[])
            ])
        ])
    ])


async def main():
    tag = Tag.parse_obj(tag_data)
    tag = await Resolver().resolve(tag)
    print(tag.json(indent=4))
    

asyncio.run(main())