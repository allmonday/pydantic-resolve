.. pydantic-resolve documentation master file, created by
   sphinx-quickstart on Sat Jun 10 14:43:37 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to pydantic-resolve's documentation!
====

Pydantic-resolve 是一个轻量级的工具库

它这么几个功能：

1. 从各个数据源来构建嵌套数据结构。
2. 利用dataloader解决多层嵌套结构中会出现的N+1查询问题。
3. 拼装出类似graphql 的多层级嵌套数据，却不用引入整套 graphql 框架。


最简单用法
----

它最简单的使用方法之一是客串一下getter 方法：

.. code-block:: python
   :linenos:

   import asyncio
   from pydantic import BaseModel
   from pydantic_resolve import resolve

   class User(BaseModel):
      name: str
      age: int

      greeting: str = ''
      def resolve_greeting(self):
         return f"hello, i'm {self.name}, {self.age} years old."

   async def main():
      user = User(name="tangkikodo", age=20)
      user = await resolve(user)
      print(user.json())
   
.. code-block:: shell

   {
      "name": "tangkikodo", 
      "age": 19,
      "greeting": "hello, i'm tangkikodo, 19 years old."
   }
      

异步地拼接数据
----

稍微复杂一点的用法是拼接多个异步请求的数据, 下面的例子假设一个异步查询返回了当前用户的所有Friend 信息:

.. code-block:: python
   :linenos:

   import asyncio
   from pydantic import BaseModel
   from pydantic_resolve import resolve

   async def search_friend(name: str):
         await asyncio.sleep(1)
         return [Friend(name="tom"), Friend(name="jerry")]

   class User(BaseModel):
      name: str
      age: int

      friends: List[Friend] = []
      async def resolve_friends(self):
         return await search_friend(self.name)

   class Friend(BaseModel):
      name: str

   async def main():
      user = User(name="tangkikodo", age=20)
      user = await resolve(user)
      print(user)
      
.. code-block:: shell

   {
      "name": "tangkikodo", 
      "age": 19,
      "friends": [{"name": "tom"}, {"name": "jerry"}]
   }

在这里需要提一个库的缺点，因为是递归解析，如果被resolve 的对象是祖先节点的类型之一的话，就会引起递归查询。

如果熟悉graphql的话，在graphql query中可以通过控制query 语句的查询深度来解决这个问题。

例如：

.. code-block:: python
   :linenos:

   class B(BaseModel):
      node_a: Optional[A] = None
      async def resolve_value_1(self):
         print(f"resolve a, {time() - t}")
         await asyncio.sleep(1)  # sleep 1
         return A()

   class A(BaseModel):
      node_b: Optional[B] = None
      async def resolve_node_b(self):
         print(f"resolve b, {time() - t}")
         await asyncio.sleep(1)
         return B()

   async def main():
      a = A()
      result = await resolve(a)
      print(result.json())
      print(f'total {time() - t}')


.. code-block:: shell

   resolve b, 0.002000570297241211
   resolve a, 1.0030534267425537
   resolve b, 2.018220901489258
   resolve a, 3.0302889347076416
   resolve b, 4.0445239543914795


于是就会反复递归, 要是没有退出条件(返回 None 或者 []) 的话就会导致死循环。

结合 dataloader
----

更加复杂的用法是引入dataloader, 以上面 User 为例，如果我需要resolve 十个 User对象的列表的话，那么每次resolve_friends 都会发起一次请求，
这就是大家所说的 N+1 查询问题。

而解决方法是依靠dataloader，改造一下代码：

.. code-block:: python
   :linenos:

   import asyncio
   from typing import List
   from pydantic import BaseModel
   from pydantic_resolve import Resolver
   from aiodataloader import DataLoader

   from pydantic_resolve.resolver import LoaderDepend

   class FriendLoader(DataLoader):
      async def batch_load_fn(self, names):
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

      greeting: str = ''
      def resolve_greeting(self):
         return f"hello, i'm {self.name}, {self.age} years old."
      
      friends: List[Friend] = []
      def resolve_friends(self, loader=LoaderDepend(FriendLoader)):
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

这里我们引入了 Resolver 类，因为需要在内部使用contextvars 来处理 loader实例，所以必须封装到一个对象内。

.. code-block:: shell

   [
      User(name='tangkikodo', age=19, greeting="hello, i'm tangkikodo, 19 years old.", friends=[Friend(name='tom'), Friend(name='jerry')]),
      User(name='john', age=21, greeting="hello, i'm john, 21 years old.", friends=[Friend(name='mike'), Friend(name='wallace')]),
      User(name='trump', age=59, greeting="hello, i'm trump, 59 years old.", friends=[Friend(name='sam'), Friend(name='jim')]),
      User(name='sally', age=21, greeting="hello, i'm sally, 21 years old.", friends=[Friend(name='sindy'), Friend(name='lydia')]),
      User(name='some one', age=0, greeting="hello, i'm some one, 0 years old.", friends=[])
   ]

从结果中能看到，我们没并没有提前收集所有待查询的User 信息，而是让 pydantic-resolve 利用dataloader在解析的过程中自动收集，然后把返回值设置回去。

而整个过程只执行了一次查询。

如果熟悉graphql 的话，会知道就算数据再深一层，例如Friend 要再查询自己的关联学校信息 List[School]，利用dataloader也只需要额外执行一次查询就行了。

Resolver里dataloader实例化方式 和 graphene 或者 strawberry 里面的有所不同，在后两者中，为了让每次请求都有全新的loader， 会在middleware 里面统一实例化。

这么做有两个问题：

1. 使用loader 必须在middleware里面添加实例化代码，使得loader相关的代码分散在不同的地方，增加维护成本
2. 在middleware中实例化所有要用的loader, 会出现创建了之后，后续的handler 中压根没用到的可能，属于一种浪费。
3. 一些临时性的，没法复用的loader， 也需要添加到middleware 中，使其变得冗长。

在pydantic-resolve 中，loader 会被 Resolver管理起来，只有真正被用到的时候才会进行实例化并且缓存。 因此降低了loader 使用的心智负担和代码成本。用户可以随心所欲地创建各种一次性的dataloader类。


更多 ...
-----

查看结合了db 和 fastapi的完整样例：
https://github.com/allmonday/pydantic-resolve/tree/master/examples/fastapi_demo



Indices and tables
====

* :ref:`genindex`
.. * :ref:`modindex`
* :ref:`search`
