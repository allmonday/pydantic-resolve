from pydantic import BaseModel
from pydantic_resolve import Resolver

class Tree(BaseModel):
    name: str
    number: int
    description: str = ''
    def resolve_description(self):
        return f"I'm {self.name}, my number is {self.number}"
    children: list['Tree'] = []


tree = dict(
    name='root',
    number=1,
    children=[
        dict(
            name='child1',
            number=2,
            children=[
                dict(
                    name='child1-1',
                    number=3,
                ),
                dict(
                    name='child1-2',
                    number=4,
                ),
            ]
        )
    ]
)

async def main():
    t = Tree.parse_obj(tree)
    t = await Resolver().resolve(t)
    print(t.json(indent=4))

import asyncio
asyncio.run(main())