# Pydantic-resolve

[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)


> If you are fan of GraphQL and want to quickly build nested data structures without any invasion, give it a try.
>
> If you want to use aiodataloader conveniently and effortlessly, give it a try.
> 
> Using pydantic-resolve with FastAPI (response_model & generating client), will greatly improve your development efficiency.

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
```

- Full-feature [example](./examples/6_sqlalchemy_loaderdepend_global_filter.py) which includes `dataloader`, `LoaderDepend` and global `loader_filters`
- Helps you asynchoronously, resursively resolve a pydantic object (or dataclass object)
- When used in conjunction with aiodataloader, allows you to easily generate nested data structures without worrying about generating N+1 queries.
- say byebye to contextvars when using dataloader.
- Inspired by [GraphQL](https://graphql.org/) and [graphene](https://graphene-python.org/)


## Some documentations.
- [Reason](./doc/reason-en.md)
- [How LoaderDepend works](./doc/loader-en.md)
- [Comparsion with common solutions](./doc/compare-en.md)

## Install

```shell
pip install pydantic-resolve

pip install "pydantic-resolve[dataloader]"  # install with aiodataloader
```

imports

```python
from pydantic_resolve import (
    Resolver, LoaderDepend,      # handle schema resolver with DataLoader
    resolve                      # handle simple resolve task
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

1. Define DataLoaders, it will run the batch query without generating the `N+1 query` issue:

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

2. Define schemas, and resolver methods, and declare related dataloader:

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
    def resolve_feedbacks(self, feedback_loader=LoaderDepend(FeedbackLoader)):  
        # LoaderDepend will manage contextvars for you
        return feedback_loader.load(self.id)

    class Config:
        orm_mode = True

class TaskSchema(BaseModel):
    id: int
    name: str
    comments: Tuple[CommentSchema, ...]  = tuple()
    def resolve_comments(self, comment_loader=LoaderDepend(CommentLoader)):
        return comment_loader.load(self.id)

    class Config:
        orm_mode = True
```

3. then... resolve it, and you will get all you want:

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

For more examples, please explore [examples](./examples/) folder.

## Comparison with Common Solutions

### Comparison with GraphQL

1. The advantages of GraphQL are 1. convenient for building nested structures, 2. clients can easily generate query subsets. It is very suitable for building public APIs that meet flexible changes.
2. However, many actual businesses in the frontend actually just follow the requirements (fetch the whole set) without the need for flexible selection. The convenience brought by GraphQL is more reflected in the flexible construction of nested structures.
3. GraphQL requires the client to maintain the query statement. Compared with the method of seamless connection between the frontend and backend through openapi.json and tool-generated clients, maintaining these query statements in the frontend and backend integrated architecture is repetitive work.
4. In order to meet the needs of access control, defining APIs one by one through RESTful is more clear and direct than controlling everything through a global Query and Mutation.
5. Pydantic-resolve just meets the need for flexible construction of nested structures. It does not need to introduce a series of concepts and settings like GraphQL. It is very lightweight and non-intrusive. All functions can be achieved by simply resolving.
6. Pydantic-resolve can hide the initialization logic of Dataloader while keeping it lightweight, avoiding the trouble of maintaining Dataloader in multiple places in GraphQL.
7. Pydantic-resolve also provides support for global loader filters, which can simplify a lot of code in some business logic. If the keys of Dataloader are considered equivalent to the join on conditions of relationship, then loader_filters is similar to other filtering conditions elsewhere.

> Conclusion:
> 1. GraphQL is more suitable for public APIs.
> 2. For projects where the frontend and backend are treated as a whole, RESTful + Pydantic-resolve is the best way to quickly and flexibly provide data structures.

### Comparison with ORM Relationship

1. Relationship provides ORM-level nested query implementation, but it defaults to using lazy select, which will cause many query times, and when used asynchronously, you need to manually declare code such as `.option(subquery(Model.field))`.
2. The foreign key of the relationship determines that no additional filtering conditions can be provided during the associated query (even if it can, it is a costly approach).
3. The biggest problem with relationship is that it makes the ORM Model and schema code coupled. The nested query that schema wants to do will invade the ORM Model layer.
4. Pydantic-resolve does not have this problem. No relationship needs to be defined at the ORM layer, and all join logic is solved through dataloader batch queries. And through the global loader_filters parameter, additional global filtering conditions can be provided.

> Conclusion:
> 1. The flexibility of the relationship solution is low, and it is not easy to modify. The default usage will produce foreign key constraints. It is not friendly to projects with frequent iterations.
> 2. Pydantic-resolve is completely decoupled from the ORM layer and can meet various needs by flexibly creating Dataloader.

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