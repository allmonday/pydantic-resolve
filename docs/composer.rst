.. _composer:


Example 1:拼接组合数据
====

稍微复杂一点的用法是拼接多个异步请求的数据, 下面的例子假设使用异步查询返回了当前用户的所有Friend 信息:

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
      print(user.json())
      
.. code-block:: shell

   {
      "name": "tangkikodo", 
      "age": 19,
      "friends": [{"name": "tom"}, {"name": "jerry"}]
   }

.. attention:: 

    在这里需要提一个注意点，因为是递归解析，如果resolve 出来的对象类型是祖先节点的类型之一的话，会引起递归查询，导致resolve 一直无法退出。

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


于是就会导致A,B反复递归, 要是没有退出条件(返回 None 或者 []) 的话就会导致死循环。

.. code-block:: shell

   resolve b, 0.002000570297241211
   resolve a, 1.0030534267425537
   resolve b, 2.018220901489258
   resolve a, 3.0302889347076416
   resolve b, 4.0445239543914795
   ...
   ...



.. hint:: 

    如果熟悉graphql的话，在graphql query中是通过控制query 语句的查询深度来解决这类问题的

