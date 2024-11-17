# ERD 驱动开发

ERD - Entity Relationship Diagram 实体关系图

对后端程序员来说这是一个很熟悉的概念, 很多数据库工具都有 ERD 可视化的功能.

ERD 本身可以是一个更加抽象的概念, 可以脱离具体数据库实现。它描述了实体和实体之间的关系, 所以许多产品经理也会用 ERD 来描述产品的核心数据关系.

因此对 ERD 是贯穿产品设计和产品实现的一个重要工具, 如果 **ERD 的结构可以在所有环节中维持清晰**, 那就能让产品更加可维护和可扩展。

我们先从已有的一些开发手段讲起， 说说他们的能力和局限。 先从关系型数据的获取开始。

## 从 SQL， ORM， 到 GraphQL

### SQL

使用 SQL 做 join 查询的时候， 如果关联的是一对多的表，那么就会引起笛卡尔积数量增加的情况。

```sql
select * from company join office on office.company_id = company.id
```

SQL 的结果是一张表， 所以关联的数据需要转换成聚合计算的结果。

```sql
select company.id, company.name, count(office.id), sum(office.charge)
    from company join office on office.company_id = company.id
    groupby company.id
```

### ORM

如果需要获取关联信息的话， 就会使用到 ORM， 在 ORM 中定义 relationship 之后， 就能获取到关联的对象。

以常用的 sqlalchemy 为例。

```python
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    # 定义 relationship
    posts = relationship("Post", back_populates="user")

class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))

    # 定义 relationship
    user = relationship("User", back_populates="posts")

rows = session.query(User).options(joinedload(User.posts)).all()
```

对于关联数据的获取， 可以通过多种 lazy 选项来调整， select 在对 User 循环时会引起 N+1 查询， joined, subquery 则会提前将数据查询加载好。 这些选项的调整是需要开发去关注来避免性能问题的。

但同时 **ORM 也伴随了一些局限**， 如果有些数据不是在数据库中，比如需要从某个第三方 API， 或者本地文件中获取，就没法享受到自动关联的便利了。

### GraphQL

GraphQL 的出现提供了一种 “新的” 思路， 它抽象了 DataLoader 的概念， 使用 `async def batch_loadn_fn(keys)` 的通用格式来定义输入参数和返回数据， 用户可以自己决定实现方式。

以数据库为例, 可以使用 `where .. in ..` 来批量查找。

```sql
select * from post where user_id in (1, 2, 3)
```

然后将获取的数据在代码中 groupby `post.user_id` 的逻辑做聚合。

如果是第三方 API 的话， 只要简单发起一次异步调用。

```python
async def batch_load_fn(user_ids):
    posts = await get_posts_by_user_ids(user_ids)
    return build_list(posts, user_ids, lambda x: x.user_id)
```

GraphQL 的这个机制实现了这样一种和具体实现无关的通用接口， 这也为内部优化预留了充足的空间。

但 DataLoader 的威力在 GraphQL 体系下是被限制了的。

最常见的场景是 DataLoader 默认只能通过 keys， 也就是单一的外键来关联数据， 如果要对资源做额外过滤， 会很难做。

用查询来举例， `(1, 2, 3, 4)` 是传入的 keys, `where` 条件则没有合适的手段来设置。

```sql
select * from post where post.user_id in (1,2,3,4) where post.created_at > '2021-12-12'
```

从设置的角度来看， keys 是一个个 User 对象通过 `loader.load(key)` 提供的， 而 `where` 条件是则是直接针对 loader 做的配置。

GraphQL 本身没有方便的手段来提供 `where` 参数， 比较遗憾。

### 使用 Pydantic 来定义 ERD

```python

```

### 用 DataLoader 来串联起各个 Entity

### 使业务 ERD 和代码高度一致
