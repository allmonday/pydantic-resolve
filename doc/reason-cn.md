# 为什么要弄pydantic-resolve

## 案例 

以论坛为例，有个接口返回帖子(posts)信息，然后呢，来了新需求，说需要显示帖子的 author 信息。

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

此时会有两种选择：

1. 在 posts 的 query 中 join 查询 author 信息，在返回 post 中添加诸如 author_id, author_name 之类的字段。 

    `{'post': 'v2ex', 'author_name': 'tangkikodo'}`

2. 根据 posts 的 ids ， 单独查询 author 列表，然后把 author 对象循环添加到 post 对象中。 

    `{'post':'v2ex', 'author': {'name': 'tangkikod'}}`

方法 1 中，需要去修改 query, 还需要修改post的schema. 如果未来要加新字段，例如用户头像的话，会需要修改两处。

方法 2 需要手动做一次拼接。之后增减字段都是在 author 对象的范围内修改。

所以相对来说, 方法 2 在未来的可维护性会比较好。用嵌套对象的方式可以更好的扩展和维护。

然而需求总是会变化，突然来了一个新的且奇怪的需求，要在 author 信息中添加数据，显示他最近浏览过的帖子。返回体变成了：

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

那这个时候该怎么弄呢？血压是不是有点上来了。

根据之前的方法 2, 通常的操作是在获取到authors信息后, 关联查找author的recent_posts, 拼接回authors, 再将 authors 拼接回posts。 流程类似层层查找再层层回拼。 伪代码类似：

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
莫名的会联想到callback hell, 添加新的层级都会在代码中间部分切入。

反正想想就挺麻烦的对吧。要是哪天再嵌套一层呢? 代码改起来有点费劲, 如果你此时血压有点高，那请继续往下看。

那，有别的办法么？ 这里有个小轮子也许能帮忙。

## 解决方法

`pydantic-resolve`

以刚才的例子，要做的事情分两步:

1. 定义 dataloader ，前半部分是从数据库查询，后半部分是将数据转成 pydantic 对象后返回。 伪代码，看个大概意思就好。

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

2. 定义 schema, 并且注入依赖的 DataLoaders, LoaderDepend 会管理好loader 的异步上下文缓存。

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

然后呢？

然后就没有了，接下来只要做个 post 的查询, 再简单地...resolve 一下，任务就**完成了**。

```python
posts = (await session.execute(select(Post))).scalars().all()
posts = [PostSchema.from_orm(p) for p in posts]
results = await Resolver().resolve(posts)
```

在拆分了 loader 和 schema 之后，对数据地任意操作都很简单，添加任意新的schema 都不会破坏原有的代码。

不用担心异步上下文的创建，不用再别的地方实例化DataLoader, 一切都在`pydantic-resolve`的管理之中。

就完事了。如果必须说有啥缺点的话。。必须用 async await 可能算一个