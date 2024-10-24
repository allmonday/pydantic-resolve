[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

Pydantic-resolve is a schema based, hierarchical solution for data fetching and crafting.

It can compose schemas together with resolver (and dataloader), and then expose typescript types and methods to client.

It can be a super simple alternative solution for GraphQL

![](./doc/imgs/concept.png)

**Features**:

1. with pydantic schema and instances, resolver recursively resolve uncertain nodes and their descendants.
2. nodes could be modified during post-process
3. plugable, easy to combine together and reuse.

## Install

~~User of pydantic v2, please use [pydantic2-resolve](https://github.com/allmonday/pydantic2-resolve) instead.~~

This lib supports both pydantic v1 and v2

```shell
pip install pydantic-resolve
```

## Hello world

```python
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
```

```json
{
  "name": "root",
  "number": 1,
  "description": "I'm root, my number is 1",
  "children": [
    {
      "name": "child1",
      "number": 2,
      "description": "I'm child1, my number is 2",
      "children": [
        {
          "name": "child1-1",
          "number": 3,
          "description": "I'm child1-1, my number is 3",
          "children": []
        },
        {
          "name": "child1-2",
          "number": 4,
          "description": "I'm child1-2, my number is 4",
          "children": []
        }
      ]
    }
  ]
}
```

## Documents

- **Quick start**: https://allmonday.github.io/pydantic-resolve/about/
- **API**: https://allmonday.github.io/pydantic-resolve/reference_api/
- **Demo**: https://github.com/allmonday/pydantic-resolve-demo
- **Composition oriented pattern**: https://github.com/allmonday/composition-oriented-development-pattern

## Sponsor

If this code helps and you wish to support me

Paypal: https://www.paypal.me/tangkikodo

## Discussion

[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)
