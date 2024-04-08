[![pypi](https://img.shields.io/pypi/v/pydantic-resolve.svg)](https://pypi.python.org/pypi/pydantic-resolve)
[![Downloads](https://static.pepy.tech/personalized-badge/pydantic-resolve?period=month&units=abbreviation&left_color=grey&right_color=orange&left_text=Downloads)](https://pepy.tech/project/pydantic-resolve)
![Python Versions](https://img.shields.io/pypi/pyversions/pydantic-resolve)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/allmonday/6f1661c6310e1b31c9a10b0d09d52d11/raw/covbadge.json)
[![CI](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml/badge.svg)](https://github.com/allmonday/pydantic_resolve/actions/workflows/ci.yml)

Pydantic-resolve is a schema based, hierarchical solution for fetching and crafting data.

It combines the advantages of restful and graphql.


![img](docs/images/intro.jpeg)


Advantages:
1. use declaretive way to define view data, easy to maintain and develop
2. enhance the traditional restful response, to support gql-like style data structure.
3. provide post_method and other tools to craft resolved data.


[Discord](https://discord.com/channels/1197929379951558797/1197929379951558800)

## Install

> If you are using pydantic v2, please use [pydantic2-resolve](https://github.com/allmonday/pydantic2-resolve) instead.


```shell
pip install pydantic-resolve
```


## Concepts from GraphQL to Pydantic-resolve

```gql
query {
    MyBlogSite {
        name
        blogs {
            id
            title
            comments {
                id
                content
            }
            # comment_count
        }
        # comment_count
    }
}
```

This is how we do queries in GraphQL, dive by describing schema and field names.

Assuming `comment_count` is a extra field (length of comment), which is required and calculated by client after fetching the data.

client side so need to iterate over the blogs to get the length and the sum, which is boring (things gets worse if the structure is deeper).

In pydantic-resolve, we can handle comment_count at server side, by transforming the query into pydantic schemas and attach some resolve, post methods.


```python
import blog_service as bs
import comment_service as cs

class MySite(BaseModel):
    blogs: list[MySiteBlog] = []
    async def resolve_blogs(self):
        return await bs.get_blogs()

    comment_count: int = 0
    def post_comment_count(self):
        return sum([b.comment_count for b in self.blogs])

# -------- inherit and extend ----------
class MySiteBlog(bs.Blog):  
    comments: list[cs.Comment] = []
    def resolve_comments(self, loader=LoaderDepend(cs.blog_to_comments_loader)):
        return loader.load(self.id)

    comment_count: int = 0
    def post_comment_count(self):
        return len(self.comments)
        
async def main():
    my_blog_site = MyBlogSite(name: "tangkikodo's blog")
    my_blog_site = await Resolver().resolve(my_blog_site)
```

schemas , query functions and loader functions are provided by entity's service modules. 

So that we can declare customrized schema by simpily **INHERIT** and **EXTEND** from base schemas.

> This just sounds like columns of values (inherit) and of foreign keys (extend) in concept of relational database.

After transforming GraphQL query into pydantic schemas, post calculation become dead easy, and no more iterations.

> Collector is a powerful feature for adjusting data structures. https://allmonday.github.io/pydantic-resolve/reference_api/#collector


## API Reference
https://allmonday.github.io/pydantic-resolve/reference_api/

## Composition oriented development-pattern (wip)
https://github.com/allmonday/composition-oriented-development-pattern


## Unittest

```shell
poetry run python -m unittest  # or
poetry run pytest  # or
poetry run tox
```

## Coverage

```shell
poetry run coverage run -m pytest
poetry run coverage report -m
```
