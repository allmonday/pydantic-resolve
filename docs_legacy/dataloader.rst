.. _dataloader:

Example 2:搭配 DataLoader 处理多层N+1 查询
====

回顾上一个例子

.. code-block:: python

   class User(BaseModel):
      name: str
      age: int

      friends: List[Friend] = []
      async def resolve_friends(self):
         return await search_friend(self.name)

   async def main():
      users = [User(name=f"tangkikodo-{i}", age=20+i) for i in range(10)]
      user = await resolve(users)


如果我需要resolve N个User对象的列表的话，那么每次resolve_friends 都会发起一次请求，这就是所谓的 N+1 查询问题。 这个问题可以通过引入 aiodataloader 来解决。

改造一下代码：

1. 添加async def friends_batch_load_fn 方法, 具体用法参考 aiodataloader 文档 `link`_
2. 引入Resolver, LoaderDepend

.. hint::
    - Resolver和 LoaderDepend 用来维护管理contextvar和loader 的实例化
    - 1.0.0 以后支持直接使用batch_load_fn作为参数, 低版本需要声明继承DataLoader

.. _link: https://github.com/syrusakbary/aiodataloader#batch-function


.. code-block:: python
   :linenos:

   import asyncio
   from typing import List
   from pydantic import BaseModel
   from pydantic_resolve import Resolver

   from pydantic_resolve.resolver import LoaderDepend

    async def friends_batch_load_fn(names):
        mock_db = {
            'tangkikodo': ['tom', 'jerry'],
            'john': ['mike', 'wallace'],
            'trump': ['sam', 'jim'],
            'sally': ['sindy', 'lydia'],
        }
        result = []
        for name in names:
            friends = mock_db.get(name, [])
            friends = [Friend(name=f) for f in friends]
            result.append(friends)
        return result

   class Friend(BaseModel):
      name: str

   class User(BaseModel):
      name: str
      age: int
      
      friends: List[Friend] = []
      def resolve_friends(self, loader=LoaderDepend(friends_batch_load_fn)):
         return loader.load(self.name)

   async def main():
      users = [
         User(name="tangkikodo", age=19),
         User(name='john', age=21),
         User(name='trump', age=59),
         User(name='sally', age=21),
         User(name='some one', age=0),
      ]
      users = await Resolver().resolve(users)
      print(users)

   asyncio.run(main())

.. code-block:: shell

   [
      User(name='tangkikodo', age=19, friends=[Friend(name='tom'), Friend(name='jerry')]),
      User(name='john', age=21, friends=[Friend(name='mike'), Friend(name='wallace')]),
      User(name='trump', age=59, friends=[Friend(name='sam'), Friend(name='jim')]),
      User(name='sally', age=21, friends=[Friend(name='sindy'), Friend(name='lydia')]),
      User(name='some one', age=0, friends=[])
   ]

从结果中能看到，我们没并没有提前收集所有待查询的User 信息，而是让 pydantic-resolve 利用dataloader在解析的过程中自动收集，然后把返回值设置回去。

整个过程只执行了一次查询。

.. hint::

    如果熟悉graphql 的话，会知道就算数据再深一层，例如Friend 要再查询自己的关联学校信息 List[School]，利用dataloader也只需要额外执行一次查询就行了。

Resolver里dataloader实例化方式 和 graphene 或者 strawberry 里面的有所不同，在后两者中，为了让每次请求都有全新的loader， 会在middleware 里面统一实例化。

这么做有两个问题：

1. 使用loader 必须在middleware里面添加实例化代码，使得loader相关的代码分散在不同的地方，增加维护成本
2. 在middleware中实例化所有要用的loader, 会出现创建了之后，后续的handler 中压根没用到的可能，属于一种浪费。
3. 一些临时性的，没法复用的loader， 也需要添加到middleware 中，使其变得冗长。

在pydantic-resolve 中，loader 会被 Resolver管理起来，只有真正被用到的时候才会进行实例化并且缓存。 因此降低了loader 使用的心智负担和代码成本。用户可以随心所欲地创建各种一次性的dataloader类。
