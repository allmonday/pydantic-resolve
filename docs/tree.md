# Tree, self-reference structure

## Build a tree with dataloader

```python
from __future__ import annotations
import asyncio
from typing import List
from pydantic import BaseModel
from pydantic_resolve import Resolver, LoaderDepend, build_list
from aiodataloader import DataLoader


root = { 'id': 1, 'content': 'root' }
records = [
    {'id': 2, 'parent': 1, 'content': '2'},
    {'id': 3, 'parent': 1, 'content': '3'},
    {'id': 4, 'parent': 2, 'content': '4'},
    {'id': 5, 'parent': 3, 'content': '5'},
]

class Loader(DataLoader):
    records: List[dict]
    async def batch_load_fn(self, keys):
        return build_list(self.records, keys, lambda x: x['parent'])

class Tree(BaseModel):
    id: int
    content: str
    children: List[Tree] = []

    def resolve_children(self, loader=LoaderDepend(Loader)):
        return loader.load(self.id)
    
async def main():
    tree = Tree(id=1, content='root')
    tree = await Resolver(loader_params={Loader: {'records': records}}).resolve(tree)
    print(tree.json(indent=2))

asyncio.run(main())
```

```json
{
  "id": 1,
  "content": "root",
  "children": [
    {
      "id": 2,
      "content": "2",
      "children": [
        {
          "id": 4,
          "content": "4",
          "children": []
        }
      ]
    },
    {
      "id": 3,
      "content": "3",
      "children": [
        {
          "id": 5,
          "content": "5",
          "children": []
        }
      ]
    }
  ]
}
```

## Construct the path with parent

if we want to visit parent node to build a full path field, use the `parent`.

```python hl_lines="10"
class Tree(BaseModel):
    id: int
    content: str
    children: List[Tree] = []

    def resolve_children(self, loader=LoaderDepend(Loader)):
        return loader.load(self.id)
    
    path: str = ''
    def resolve_path(self, parent):
        if parent:
            return f'{parent.path}/{self.content}'
        else:
            return self.content
```

then it's done

```json
{
  "id": 1,
  "content": "root",
  "path": "root",
  "children": [
    {
      "id": 2,
      "content": "2",
      "path": "root/2",
      "children": [
        {
          "id": 4,
          "content": "4",
          "path": "root/2/4",
          "children": []
        }
      ]
    },
    {
      "id": 3,
      "content": "3",
      "path": "root/3",
      "children": [
        {
          "id": 5,
          "content": "5",
          "path": "root/3/5",
          "children": []
        }
      ]
    }
  ]
}
```

## Sum up from bottom to top
Calculate the sum for each node by just declearing a post_method.

```python hl_lines="12-13"
from __future__ import annotations
import asyncio
from pydantic import BaseModel
from typing import List
from pydantic_resolve import Resolver

class Tree(BaseModel):
    count: int
    children: List[Tree] = []
    
    total: int = 0
    def post_total(self):
        return self.count + sum([c.total for c in self.children])


tree = dict(count=10, children=[
    dict(count=9, children=[]),
    dict(count=1, children=[
        dict(count=20, children=[])
    ])
])

async def main():
    t = await Resolver().resolve(Tree(**tree))
    print(t.json(indent=2))


asyncio.run(main())
```


```json hl_lines="7 15 18 21"
{
  "count": 10,
  "children": [
    {
      "count": 9,
      "children": [],
      "total": 9
    },
    {
      "count": 1,
      "children": [
        {
          "count": 20,
          "children": [],
          "total": 20
        }
      ],
      "total": 21
    }
  ],
  "total": 40
}
```
