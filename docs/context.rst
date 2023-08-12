.. _context:


2. 通过Context传递参数
====

在上一个例子中，如果希望search的参数可以从外部传入的话， 可以使用`context` 

.. code-block:: python
   :linenos:
   :emphasize-lines: 5, 7, 17, 25

   import asyncio
   from pydantic import BaseModel
   from pydantic_resolve import resolve

   async def search_friend(name: str, gender: str):
         await asyncio.sleep(1)  # search friends of tangkikodo
         if gender == 'male':
            return [Friend(name="tom"), Friend(name="peter")]
         else:
            return [Friend(name="marry"), Friend(name="cary")]

   class User(BaseModel):
      name: str
      age: int

      friends: List[Friend] = []
      async def resolve_friends(self, context):
         return await search_friend(self.name, context['gender'])

   class Friend(BaseModel):
      name: str

   async def main():
      user = User(name="tangkikodo", age=20)
      user = await Resolver(context={'gender': 'male'}).resolve(user)
      print(user.json())
      
.. code-block:: shell
   :linenos:
   :emphasize-lines: 4

   {
      "name": "tangkikodo", 
      "age": 19,
      "friends": [{"name": "tom"}, {"name": "peter"}]
   }

