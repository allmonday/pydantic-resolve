# Power of Inheritance, better architecture.

Pydantic-resolve can plays well as a `BFF` or `Anti-corruption` layer, meeting all view requirements and keeping `service layers` stable at the same time.

It is recommended to read this repo: [Composition oriented development pattern](https://github.com/allmonday/composition-oriented-development-pattern) for details.

## Create service
Let's review the `Blog` and `Comment`, this time we use them to defined the types of source data.

let's split them apart as `blog_service` and `comment_service`.

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

`blog_service` includes schema and main query, `comment_service` includes schema and data loader.

> main query provides the root data

## Create controller
Next, in `my-site` controller, we'll compose them together into `MyBlogSite` again, but by inheritance.

Structrues:

- **controller**
    - my_site
- **service**
    - blog_service.py
    - comment_service.py
    - user_service.py (later)

my_site.py
```python hl_lines="10"
import service.blog_service as blog_service
import service.comment_service as comment_service

class MySite(BaseModel):
    blogs: list[MySiteBlog] = []
    async def resolve_blogs(self):
        return await get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])

class MySiteBlog(blog_service.Blog):
    comments: list[comment_service.Comment] = []
    def resolve_comments(self, loader=LoaderDepend(blog_to_comments_loader)):
        return loader.load(self.id)
    
    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)
```

We don't need to declare `id` and `title`, they now inherits from `Blog`.

With the help of inheritance, we get the capability to build flexible schemas (in controller layer) based on stable base schema from services.

## Add user service
Let's continue adding a new service: `user-service`, it provides User schema and user data loader.

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

Modify comment, add user_id into comment model

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

## Add User into Controller

after declaring `MySiteComment` with inheriting from `Comment`, and a simple user_loader.

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

You'll get the output:

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
      "comment_count": 2
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
      "comment_count": 2
    }
  ],
  "comment_count": 4
}
```

So easy, isn't it?


If you want to customrize(pick) fields, you can:
- use @model_config and Exclude to hide it
- use ensure_subset(Base)