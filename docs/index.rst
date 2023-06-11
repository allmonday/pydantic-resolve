Pydantic-resolve 使用手册 
====

Pydantic-resolve 是一个轻量级的工具库，用来构建多层嵌套数据。

它这么几个功能：

1. 从各个数据源来构建嵌套数据结构。
2. 利用dataloader解决多层嵌套结构中会出现的N+1查询问题。
3. 拼装出类似graphql 的多层级嵌套数据，却不用引入整套 graphql 框架。


安装
----

.. code-block:: shell

   pip install pydantic-resolve
   
   # or
   pip install "pydantic-resolve[dataloader]"  # install with aiodataloader

source: https://github.com/allmonday/pydantic-resolve


开始吧
----

它最简单的使用方法之一是客串一下getter 方法，分两个步骤：

1. 先在 User 类中定义greeting 类型和默认值，再添加 resolve_greeting 方法
2. 使用resolve 方法处理，获得计算后的结果 

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
      


完整样例
----

查看结合了db 和 fastapi的完整样例：
https://github.com/allmonday/pydantic-resolve/tree/master/examples/fastapi_demo


场景和使用方法：
====

.. * :ref:`modindex`
* :ref:`composer`
* :ref:`dataloader`


更多：
====

* :ref:`search`
* :ref:`changelog`

