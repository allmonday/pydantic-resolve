# Why create a new library?

I am a user of FastAPI (and starlette). Before writing pydantic-resolve, I used two methods to write APIs:

- GraphQL, using a niche python library pygraphy and a mainstream library strawberry-python
- FastAPI's native restful style interface, combined with SQLAlchemy

The combination of GraphQL and pydantic inspired the creation of pydantic-resolve.

## Inspiration from GraphQL

The original intention of using GraphQL was to provide a flexible backend data interface. Once the Entity and Relationship are clearly defined, GraphQL can provide many general query functions. (Just like there are many tools now that can directly query the db with GraphQL)

In the early stages of the project, this saved a lot of development time for the backend. Once the relationships between the data were defined, all object data could be provided to the frontend, allowing the frontend to assemble the data themselves. Initially, the collaboration was very pleasant.

But as the project became more complex, the cost of maintaining a layer of data transformation on the frontend began to rise. For example, the frontend might use a roundabout way to query data, such as querying team -> project because the project object did not define a filter by has_team condition. Then the frontend would convert the data into a list of projects. As the functionality iterated more, the frontend began to complain that the queries were too slow. I gradually realized that the claim that GraphQL allows the frontend and backend to communicate without communication is an illusion.

```graphql
query {
    team {
        project {
            id
            name
        }
    }
}
```

Another situation is that the backend's previous schema definition becomes chaotic. For example, the project will add many associated objects or special calculated values as it iterates. But for the query, this information is not all that should be focused on, and sometimes it is unclear how to write the query.

```graphql
query {
    project {
        id
        name
        teams { ... }
        budgets { ... }
        members { ... }
    }
}
```

The last straw that broke GraphQL was permission control. Those who have done permission control with GraphQL naturally understand that implementing permission control based on nodes is completely unrealistic. The final compromise was to use the root node of the query to expose different entry points, which ended up being similar to the solution under the restful architecture. Entry_1 and entry_2 were isolated, so the originally envisioned flexible query completely turned into static schemas.

```graphql
query {
    entry_1 {
        project {
            name
        }
    }

    entry_2 {
        team {
            name
            project {
                name
            }
        }
    }
}
```

This process gave me some insights:

- GraphQL's data description method is very friendly to the frontend. The hierarchical nested structure makes data rendering convenient. (But it is easy to form non-reusable schemas on the backend)
- The graph model in GraphQL, combined with the ER model, can reuse a large number of Entity queries. Dataloader can optimize N+1 queries
- Frontend data combination is a wrong practice. Data combination is also a business content, and it can only be maintained for a long time if it is managed uniformly on the business side
- Frontend querying GraphQL queries is also a wrong practice. It will form historical baggage and hinder the backend from refactoring and adjusting the code. In the end, both sides will have dirty code.

## Inspiration from FastAPI and pydantic

After being exposed to FastAPI and pydantic, what impressed me the most was the ability to generate openapi with the help of pydantic, and then generate the frontend typescript sdk. (Of course, this is not unique to FastAPI)

It directly reduced the cost of frontend and backend integration by an order of magnitude. All backend interface changes can be perceived by the frontend. For example, although GraphQL had many tools to provide type support for queries, it still ultimately required writing queries.

After using FastAPI, the frontend became

```js
const projects = await client.BusinessModuleA.getProjects()
```

such a simple and crude query.

The problem that followed was: **How to construct a data structure that is friendly to the frontend like GraphQL**??

Using SQLAlchemy's relationship can obtain data with a relational structure, but it often requires re-traversing the data to adjust the data and structure.

If the adjustment is written into the query, it will lead to a large number of query statements that cannot be reused.

So it fell into a contradictory state.

The official recommendation is to write a pydantic class (or dataclass) that is very similar to the model definition, and this pydantic object receives the orm query results.

I always felt that this process was very redundant. If the data obtained was different from what I expected, I would need to traverse the data again to make adjustments. For example, after defining Item and Author

```python
class Item(BaseModel):
    id: int
    name: str

class Author(BaseModel):
    id: int
    name: str
    items: List[Item]
```

If I need to filter Items based on some complex business logic for business needs, or create a new field in Item based on business logic, I need to expand the loop for the authors and items returned by the ORM query.

```python
for author in authors:
    business_process(author.items)

    for item in author.items:
        another_business_process(item)
        ...
```

It is okay if the number of layers is small. If the content to be modified is large or the number of layers is deep, it will lead to similar code readability and maintainability issues.

Inspired by grephene-python, an idea came up, why not define a resolve_method in place?

```python
class Item(BaseModel):
    id: int
    name: str
    new_field: str = ''
    def resolve_new_field(self):
        return business_process(self)

class Author(BaseModel):
    id: int
    name: str
    items: List[Item]
    def resolve_items(self):
        return business_process(self.items)
```

In this way, all operational behaviors are defined inside the data object, and the data traversal process is left to the code to automatically traverse. When encountering the corresponding type, the internal method is executed.

The DataLoader in GraphQL is also an excellent method for obtaining hierarchical data. So can DataLoader be used to replace the ORM association?

So items became a parameter that defaults to `[]`, and ItemLoader is used to obtain data, a **declarative loading mode**

```python
class Item(BaseModel):
    id: int
    name: str
    new_field: str = ''
    def resolve_new_field(self):
        return business_process(self)

class Author(BaseModel):
    id: int
    name: str

    items: List[Item] = []
    async def resolve_items(self， loader=LoaderDepend(ItemLoader)):
        items =  await loader.load(self.id)
        return business_process(items)
```

Then, since resolve represents obtaining data, can a post hook function be added to modify the obtained data after all resolve methods are completed?

So post_methods and post_default_handler were added.

At this point, it is almost the entire story of pydantic-resolve.

My development mode became:

- First design the business model and define the ER model
- Define models, pydantic classes, and DataLoaders
- Describe the data structure required by the business through inheritance and extension, use DataLoader to obtain data, and use post methods to adjust the data
- Use FastAPI and TypeScript sdk generator to transmit methods and type information to the frontend

This mode has strong adaptability to the situation of frequent adjustments in the early stage of the business. Adjustments to data relationships only require re-declaring combinations or adding new DataLoaders.

