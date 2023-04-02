Why Use pydantic-resolve?

## Case Study

Let's take a forum as an example. There is an API that returns information about posts, and then a new requirement comes up that says the author information of the post needs to be displayed.

```json
[
  {
    "id": 1,
    "post": "v2ex",
    "author": {
      "name": "tangkikodo",
      "id": 1
    }
  },
  {
    "id": 2,
    "post": "v3ex",
    "author": {
      "name": "tangkikodo2",
      "id": 1
    }
  }
]
```

At this point, there are two options:

1. Join the author information in the query of posts and add fields such as author_id and author_name to the returned post.
    `{'post': 'v2ex', 'author_name': 'tangkikodo'}`
2. Query the author list separately based on the ids of the posts, and then loop through the author objects and add them to the post objects.
    `{'post':'v2ex', 'author': {'name': 'tangkikod'}}`

In method 1, you need to modify the query and the schema of the post. If you need to add a new field in the future, such as the user's avatar, you will need to modify two places.
Method 2 requires manual splicing. Adding or removing fields is done within the scope of the author object.
So relatively speaking, method 2 will be more maintainable in the future. Using nested objects can better extend and maintain.

However, requirements always change, and suddenly a new and strange requirement comes up to add data to the author information, showing the posts he has recently viewed. The return body becomes:

```json
[
  {
    "id": 1,
    "post": "v2ex",
    "author": {
      "name": "tangkikodo",
      "recent_views": [
        {
          "id": 2,
          "post": "v3ex"
        },
        {
          "id": 3,
          "post": "v4ex"
        }
      ]
    }
  }
]
```

So how do you do it now? Is your blood pressure a little high?

According to the previous method 2, the usual operation is to associate and find the author's recent posts after obtaining the author information, splice it back to the author, and then splice the authors back to the posts. The process is similar to finding and splicing layer by layer. The pseudo code is as follows:

```python
# posts query
posts = query_all_posts()

# authors query
authors_ids = fetch_unique_author_id(posts)  
authors = query_author(author_ids)

recent_view_posts = fetch_recent_review_posts(author_ids)  # 新需求
recent_view_maps = calc_view_mapping(recent_view_posts)    # 新需求

# authors attach
authors = [attach_posts(a, recent_view_maps) for a in authors]
author_map = calc_author_mapping(authors)

# posts attach
posts = [attach_author(p, author_map) for p in posts]
```
It inexplicably reminds people of callback hell, and adding new levels will cut into the middle of the code.

Anyway, it's quite troublesome to think about it. What if another layer of nesting is added one day? It's a bit difficult to change the code. If your blood pressure is a bit high at this time, please continue reading.

So, is there any other way? Here is a small tool that may help.

## Solution

`pydantic-resolve`

In the example just now, there are two things to do:

1. Define the dataloader. The first part is to query from the database, and the second part is to convert the data into pydantic objects and return them. The pseudo code is just to get a rough idea.
```python


```python
class AuthorLoader(DataLoader):
    async def batch_load_fn(self, author_ids):
        async with async_session() as session:
            # query authors
            res = await session.execute(select(Author).where(Author.id.in_(author_ids)))
            rows = res.scalars().all()

            # transform into pydantic object
            dct = defaultdict(dict)
            for row in rows:
                dct[row.author_id] = AuthorSchema.from_orm(row)
            
            # order by author_id
            return [dct.get(k, None) for k in author_ids]

class RecentViewPostLoader(DataLoader):
    async def batch_load_fn(self, view_ids):
        async with async_session() as session:
            res = await session.execute(select(Post, PostVisit.visitor_id)  # join 浏览中间表
                .join(PostVist, PostVisit.post_id == Post.id)
                .where(PostVisit.user_id.in_(view_ids)
                .where(PostVisit.created_at < some_timestamp)))
            rows = res.scalars().all()

            dct = defaultdict(list)
            for row in rows:
                dct[row.visitor_id].append(PostSchema.from_orm(row))  # group 到 visitor
            return [dct.get(k, []) for k in view_ids]
```

2. Define the schema and inject the required DataLoaders. LoaderDepend will manage the asynchronous context cache of the loader.

```python
class RecentPostSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class AuthorSchema(BaseModel):
    id: int
    name: str
    img_url: str

    recent_views: Tuple[RecentPostSchema, ...] = tuple()
    def resolve_recent_views(self, loader=LoaderDepend(RecentViewPostLoader)):  
        return loader.load(self.id)
    
    class Config:
        orm_mode = True

class PostSchema(BaseModel):
    id: int
    author_id: int
    name: str

    author: Optional[AuthorSchema] = None
    def resolve_author(self, loader=LoaderDepend(AuthorLoader)):
         return loader.load(self.author_id)

    class Config:
        orm_mode = True
```

What's next?

After that, it's done. Just do a post query and resolve it simply.

```python
posts = (await session.execute(select(Post))).scalars().all()
posts = [PostSchema.from_orm(p) for p in posts]
results = await Resolver().resolve(posts)
```

After separating the loader and schema, any operation on the data is simple, and adding any new schema will not break the existing code.

No need to worry about creating asynchronous contexts or instantiating DataLoader elsewhere, everything is managed by pydantic-resolve.

That's it. If there must be a downside, it may be the need to use async await.