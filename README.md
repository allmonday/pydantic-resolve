# Pydantic-resolve

[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)


```python
import asyncio
from random import random
from pydantic import BaseModel
from pydantic_resolve import resolve

class Human(BaseModel):
    name: str
    lucky: bool = True

    async def resolve_lucky(self):
        print('calculating...')
        await asyncio.sleep(1)  # mock i/o
        return random() > 0.5

async def main():
    humans = [Human(name=f'man-{i}') for i in range(10)]
    results = await resolve(humans)
    print(results)

asyncio.run(main())

# calculating... x 10
# [
#   Human(name='man-0', lucky=False),
#   Human(name='man-1', lucky=False),
#   ...
#   Human(name='man-8', lucky=False),
#   Human(name='man-9', lucky=True)
# ]
# ```

- Helps you asynchoronously, resursively resolve a pydantic object (or dataclass object)
- When used in conjunction with aiodataloader, allows you to easily generate nested data structures without worrying about generating N+1 queries.
- say byebye to contextvars when using dataloader.
- Inspired by [GraphQL](https://graphql.org/) and [graphene](https://graphene-python.org/)

## Why create this package?
- [english version](./doc/english.md)
- [chinese version](./doc/chinese.md)

## Install

```shell
pip install pydantic-resolve
```

imports

```python
from pydantic_resolve import (
    Resolver, LoaderDepend,  # schema with DataLoader
    resolve  # simple resolve
)
```

## Feature 1, Resolve asynchoronously, recursiverly, concurrently.

```python
import asyncio
from random import random
from time import time
from pydantic import BaseModel
from pydantic_resolve import resolve

t = time()

class NodeB(BaseModel):
    value_1: int = 0
    async def resolve_value_1(self):
        print(f"resolve_value_1, {time() - t}")
        await asyncio.sleep(1)  # sleep 1
        return random()

class NodeA(BaseModel):
    node_b_1: int = 0
    async def resolve_node_b_1(self):
        print(f"resolve_node_b_1, {time() - t}")
        await asyncio.sleep(1)
        return NodeB()

class Root(BaseModel):  # [!] resolve fields concurrently
    node_a_1: int = 0
    async def resolve_node_a_1(self):
        print(f"resolve_node_a_1, {time() - t}")
        await asyncio.sleep(1)
        return NodeA()

    node_a_2: int = 0
    async def resolve_node_a_2(self):
        print(f"resolve_node_a_2, {time() - t}")
        await asyncio.sleep(1)
        return NodeA()

    node_a_3: int = 0
    async def resolve_node_a_3(self):
        print(f"resolve_node_a_3, {time() - t}")
        await asyncio.sleep(1)
        return NodeA()

async def main():
    root = Root()
    result = await resolve(root)
    print(result.json())
    print(f'total {time() - t}')

asyncio.run(main())
```

```
resolve_node_a_1, 0.002000093460083008
resolve_node_a_2, 0.002000093460083008
resolve_node_a_3, 0.002000093460083008

resolve_node_b_1, 1.0142452716827393
resolve_node_b_1, 1.0142452716827393
resolve_node_b_1, 1.0142452716827393

resolve_value_1, 2.0237653255462646
resolve_value_1, 2.0237653255462646
resolve_value_1, 2.0237653255462646

total 3.0269699096679688
```

```json
{
    "node_a_1": {"node_b_1": {"value_1": 0.912570826381839}}, 
    "node_a_2": {"node_b_1": {"value_1": 0.41784985892912485}}, 
    "node_a_3": {"node_b_1": {"value_1": 0.6148494329990393}}
}
```

### Feature 2: Integrated with aiodataloader:

`pydantic_resolve.Resolver` will handle the lifecycle and injection of loader instance, you don't need to manage it with contextvars any more.

1. Define loaders

```python
class FeedbackLoader(DataLoader):
    async def batch_load_fn(self, comment_ids):
        async with async_session() as session:
            res = await session.execute(select(Feedback).where(Feedback.comment_id.in_(comment_ids)))
            rows = res.scalars().all()
            dct = defaultdict(list)
            for row in rows:
                dct[row.comment_id].append(FeedbackSchema.from_orm(row))
            return [dct.get(k, []) for k in comment_ids]


class CommentLoader(DataLoader):
    async def batch_load_fn(self, task_ids):
        async with async_session() as session:
            res = await session.execute(select(Comment).where(Comment.task_id.in_(task_ids)))
            rows = res.scalars().all()

            dct = defaultdict(list)
            for row in rows:
                dct[row.task_id].append(CommentSchema.from_orm(row))
            return [dct.get(k, []) for k in task_ids]

```

2. Define schemas

```python
class FeedbackSchema(BaseModel):
    id: int
    comment_id: int
    content: str

    class Config:
        orm_mode = True

class CommentSchema(BaseModel):
    id: int
    task_id: int
    content: str
    feedbacks: Tuple[FeedbackSchema, ...]  = tuple()
    def resolve_feedbacks(self, feedback_loader = LoaderDepend(FeedbackLoader)):  
        # LoaderDepend will manage contextvars for you
        return feedback_loader.load(self.id)

    class Config:
        orm_mode = True

class TaskSchema(BaseModel):
    id: int
    name: str
    comments: Tuple[CommentSchema, ...]  = tuple()
    def resolve_comments(self, comment_loader = LoaderDepend(CommentLoader)):
        return comment_loader.load(self.id)

    class Config:
        orm_mode = True
```

3. Resolve it

```python
tasks = (await session.execute(select(Task))).scalars().all()
tasks = [TaskSchema.from_orm(t) for t in tasks]
results = await Resolver().resolve(tasks)  # <=== resolve schema with DataLoaders

# output
[
    {
        'id': 1,
        'name': 'task-1 xyz',
        'comments': [
            {
                'content': 'comment-1 for task 1 (changes)',
                'feedbacks': [
                    {'comment_id': 1, 'content': 'feedback-1 for comment-1 (changes)', 'id': 1},
                    {'comment_id': 1, 'content': 'feedback-2 for comment-1', 'id': 2},
                    {'comment_id': 1, 'content': 'feedback-3 for comment-1', 'id': 3}
                ],
                'id': 1,
                'task_id': 1
            },
            {
                'content': 'comment-2 for task 1',
                'feedbacks': [
                    {'comment_id': 2, 'content': 'test', 'id': 4},
                ],
                'id': 2,
                'task_id': 1
            }
        ]
    }
]

```

For more examples, please explore `examples` folder.

## Unittest

```shell
poetry run python -m unittest  # or
poetry run pytest  # or
poetry run tox
```

## Coverage 

```shell
poetry run coverage run -m pytest
poetry run coverage report -m
```
