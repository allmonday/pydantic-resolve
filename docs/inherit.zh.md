# 使用继承优化代码结构

重新回顾一下代码, 会发现 Blog 和 Comment 可以被抽出来单独定义类型, 并可以由特定的方法来提供数据

我们来将它封装到 service 中
```python
class MyBlogSite(BaseModel):
    blogs: list[Blog] = []
    async def resolve_blogs(self):
        return await get_blogs()

class Blog(BaseModel):
    id: int
    title: str

    comments: list[Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)

class Comment(BaseModel):
    id: int
    content: str
```

## 创建 service

- blog_service.py
```python
# - schema
class Blog(BaseModel):
    id: int
    title: str

blogs_table = [
    dict(id=1, title='what is pydantic-resolve'),
    dict(id=2, title='what is composition oriented development pattarn')]

# - main query
async def get_blogs(): # promise to return data which matche with the Blog schema
    return blogs_table
```

- comment_service.py
```python
# - schema
class Comment(BaseModel):
    id: int
    blog_id: int
    content: str

comments_table = [
    dict(id=1, blog_id=1, content='its interesting'),
    dict(id=2, blog_id=1, content='i need more example'),
    dict(id=3, blog_id=2, content='what problem does it solved?'),
    dict(id=4, blog_id=2, content='interesting')]

# - dataloader
async def blog_to_comments_loader(blog_ids: list[int]):
    # promise to return Comment
    return build_list(comments_table, blog_ids, lambda c: c['blog_id'])  
```

service 提供了: 

- schema 定义 
- 查询方法, 比如 get_blogs
- dataloader 方法 (一种特殊的 batch 查询)


## 创建 controller

接下来我们重新组装一下 `MySite`

- **controller**
    - my_site.py
- **service**
    - blog_service.py
    - comment_service.py

my_site.py
```python hl_lines="10"
import service.blog_service as blog_service
import service.comment_service as comment_service

class MySite(BaseModel):
    blogs: list[MySiteBlog] = []
    async def resolve_blogs(self):
        return await get_blogs()

class MySiteBlog(blog_service.Blog):
    comments: list[comment_service.Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
```

`MySiteBlog` 通过继承了 `blog_service.Blog`, 可以自动获取 Blog 的字段, 为字段复用提供了便利

在语义上, `MySiteBlog` 继承了 Blog 字段, 并额外扩展了 comments 数据

上游只需要提供满足 Blog 的数据 (MySite中的 get_blogs()), 剩下的扩展字段通过 resolve 方法来获得

使用这种方式可以灵活地扩展和组装数据

接下来让我们更进一步, 为每个 comment 增加一个 user 字段吧

## 添加 user service

同样的, 新增一个 `user_service.py` 文件

- **controller**
    - my_site.py
- **service**
    - blog_service.py
    - comment_service.py
    - user_service.py

```python
# - schema
class User(BaseModel):
    id: int
    name: int

users_table = [
    dict(id=1, name='john'),
    dict(id=2, name='kikodo')]

# - dataloader
async def user_loader(user_ids: list[int]):
    _users = [u for users_table if u in [user_ids]]
    return build_object(_users, user_ids, lambda u: u['id'])
```

修改 comment schema, 添加 user_id 信息

```python
class Comment(BaseModel):
    id: int
    blog_id: int
    user_id: int
    content: str

comments_table = [
    dict(id=1, blog_id=1, content='its interesting', user_id=1),
    dict(id=2, blog_id=1, content='i need more example', user_id=2),
    dict(id=3, blog_id=2, content='what problem does it solved?', user_id=1),
    dict(id=4, blog_id=2, content='interesting', user_id=2)]
```

## 通过继承 Comment 来添加 user 字段

```python hl_lines="19"
class MySite(BaseModel):
    blogs: list[MySiteBlog] = []
    async def resolve_blogs(self):
        return await get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])

class MySiteBlog(Blog):
    comments: list[MySiteComment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
    
    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)

class MySiteComment(Comment):
    user: Optional[User] = None
    async def resolve_user(self, loader=LoaderDepend(user_loader)):
        return loader.load(self.user_id)
```

就这样我们为每个 comment 添加了 user 信息

```json
{
  "blogs": [
    {
      "id": 1,
      "title": "what is pydantic-resolve",
      "comments": [
        {
          "id": 1,
          "blog_id": 1,
          "content": "its interesting",
          "user_id": 1,
          "user": {
            "id": 1,
            "name": "john"
          }
        },
        {
          "id": 2,
          "content": "i need more example",
          "blog_id": 1,
          "user_id": 2,
          "user": {
            "id": 2,
            "name": "kikodo"
          }
        }
      ],
    },
    {
      "id": 2,
      "title": "what is composition oriented development pattarn",
      "comments": [
        {
          "id": 3,
          "content": "what problem does it solved?",
          "blog_id": 2,
          "user_id": 1,
          "user": {
            "id": 1,
            "name": "john"
          }
        },
        {
          "id": 4,
          "content": "interesting",
          "blog_id": 2,
          "user_id": 2,
          "user": {
            "id": 2,
            "name": "kikodo"
          }
        }
      ],
    }
  ],
}
```

这样的数据组装很简单吧?


关于 pydantic-resolve 更多的功能请查看文档