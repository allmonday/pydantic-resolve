.. _changelog:

Changelog
====

v1.0.0 更新
----

现在不用额外定义继承DataLoader 的dataloader 类，直接传入 `batch_load_fn` 即可。

.. code-block:: python
   :linenos:

   async def friend_batch_load_fn(names):
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
      def resolve_friends(self, loader=LoaderDepend(friend_batch_load_fn)):
         return loader.load(self.name)

   async def main():
      users = [
         User(name="tangkikodo", age=19),
         User(name='john', age=21),
      ]
      users = await Resolver().resolve(users)
      print(users)

   asyncio.run(main())

