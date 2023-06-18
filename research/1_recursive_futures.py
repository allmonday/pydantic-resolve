import asyncio
import json
from asyncio import Future
import functools
from typing import List
from pydantic import BaseModel

class Tree(BaseModel):
    val: int
    acc: int = 0
    children: List['Tree'] = []


def reduce_method(field, func):
    def calc(fn):
        @functools.wraps(fn)
        async def wrap(**kwargs):
            tree = kwargs['tree']
            result_fut = fn(**kwargs) 

            await result_fut

            print(tree.val)
            total = func(tree)
            setattr(tree, field, total)
            return tree

        return wrap
    return calc

@reduce_method('acc', lambda tree: tree.val + sum([c.acc for c in tree.children]))
def walk_tree(tree: Tree) -> Future:  # return single future or future list
    loop = asyncio.get_event_loop()
    fut = loop.create_future()

    if not tree.children:
        fut.set_result(tree.val)
        return fut

    futs = asyncio.gather(*[walk_tree(tree=t) for t in tree.children])
    return futs

async def test():
    data = Tree(val=1, children=[
        Tree(val=2, children=[
            Tree(val=3, children=[
                Tree(val=4),
                Tree(val=4),
                Tree(val=4),
                Tree(val=4),
                Tree(val=4),
            ])
        ]),
    ])
    await walk_tree(tree=data)
    print(json.dumps(data.dict(), indent=4))


asyncio.run(test())
