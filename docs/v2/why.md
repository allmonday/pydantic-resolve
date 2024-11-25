# Why Create a New Library?

I am a user of FastAPI (and starlette). Before writing pydantic-resolve, I used two methods to write APIs:

- GraphQL, using a niche python library pygraphy and a mainstream library strawberry-python
- FastAPI's native RESTful style interface, paired with SQLAlchemy

They each have their own advantages and disadvantages.

The combination of GraphQL and pydantic inspired the creation of pydantic-resolve.

## Inspiration from GraphQL

The initial intention of using GraphQL was to provide a flexible backend data interface. Once the Entity and Relationship are clearly defined, GraphQL can provide many general query functions. (Just like there are many tools now that can directly query the database with GraphQL)

In the early stages of the project, this saved a lot of development time for the backend. Once the data relationships were defined, all object data could be provided to the frontend, allowing the frontend to combine and assemble them on their own. Initially, the collaboration was very pleasant.

But as the project became more complex, the cost of maintaining a layer of data transformation on the frontend began to rise. For example, the frontend might use a roundabout way to query data, such as querying project objects without defining a filter condition by has_team, leading the frontend to write queries like team -> project. Then the frontend would convert the data into a list of projects. As the number of iterations increased, the frontend began to complain about slow queries. I gradually realized that the claim that GraphQL allows the frontend and backend to communicate without talking was an illusion.

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

Another situation is that the backend schema becomes chaotic with iterations. For example, project will add many associated objects or special calculated values with iterations. But for the query, these information are not all should be concerned, sometimes it is not clear how to write the query.

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

The last straw that broke GraphQL was permission control. Those who have done permission control with GraphQL naturally understand. Anyway, it is completely unrealistic to implement permission control based on nodes. The final compromise was to use the root node of the query to expose different entry points, which eventually became similar to the solution under the RESTful architecture. entry_1 and entry_2 were isolated, so the flexible query originally envisioned completely turned into static schemas.

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

This process gave me some inspiration:

- The data description method of GraphQL is very friendly to the frontend. The hierarchical nested structure can facilitate data rendering. (But it is easy to form an unreusable schema on the backend)
- The graph model in GraphQL, combined with the ER model, can reuse a large number of Entity queries. dataloader can optimize N+1 queries
- Combining data on the frontend is a wrong practice. Combining data is also a business content, and it can only be maintained for a long time if it is managed uniformly on the business side
- Querying GraphQL queries on the frontend is also a wrong practice. It will form historical baggage and hinder the backend from refactoring and adjusting the code. In the end, both sides will have dirty code.

## Inspiration from FastAPI and pydantic

After getting in touch with FastAPI and pydantic, what impressed me the most was the ability to generate openapi with the help of pydantic, and then generate the frontend typescript sdk. (Of course, this is not unique to FastAPI)

It directly reduced the cost of frontend and backend docking by an order of magnitude. All backend interface changes can be perceived by the frontend. For example, although GraphQL had many tools to provide type support for queries, it still required writing queries.

After using FastAPI, the frontend became

```js
const projects: Project[] = await client.BusinessModuleA.getProjects()
```

such a simple and crude query.

The problem that followed was: **How to construct a data structure that is friendly to the frontend like GraphQL?**

Using SQLAlchemy's relationship can obtain data with relational structure, but it often requires re-traversing the data to adjust the data and structure.

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

If the number of layers is small, it is fine. If the content to be modified is large or the number of layers is deep, it will lead to reduced readability and maintainability of similar code.

Inspired by graphene-python, an idea came up. Why not define a resolve_method in place?

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

In this way, all operation behaviors are defined inside the data object, and the data traversal process is left to the code to automatically traverse. When encountering the corresponding type, the internal method is executed.

The DataLoader in GraphQL is also an excellent method for obtaining hierarchical data. So, can DataLoader be used to replace the association of ORM?

So items became a parameter with a default value of `[]`, and ItemLoader was used to obtain data. This is a **declarative loading mode**

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

This means that if I do not mount resolve_items for Author, ItemLoader will not be driven to execute. Everything is driven by the configuration of the class.

Since the fixed pydantic combination has an independent entry point, can additional parameters be added to DataLoader?

So DataLoader supports parameter settings.

Then, since resolve represents obtaining data, can a post hook function be added to modify the obtained data after all resolve methods are completed?

So post_methods and post_default_handler were added.

When dealing with data aggregation across multiple layers, passing each layer is too cumbersome, so expose and collect were added.

At this point in the iteration, it is almost the entire story of pydantic-resolve.

My development mode became:

- First design the business model and define the ER model
- Define models, pydantic classes, and DataLoaders
- Describe the data structure required by the business through inheritance and extension, use DataLoader to obtain data, and use post methods to adjust data
- Use FastAPI and TypeScript sdk generator to pass methods and type information to the frontend
- If the business logic changes, adjust or add declared content, and then synchronize the information to the frontend through the sdk

This mode has strong adaptability to the situation of frequent adjustments in the early stage of the business. For adjustments to data relationships, it is enough to re-declare the combination or add a new DataLoader.

After the project business stabilizes, there is also enough space for performance optimization, such as replacing the associated query of DataLoader with a one-time query result, and so on.

## Summary

Declare pydantic classes in a way similar to GraphQL queries on the backend to generate data structures that are friendly to the frontend (consumer side).

The backend manages all business query assembly processes, allowing the frontend to focus on UIUX, effectively dividing labor and improving the overall maintainability of the project.

Moreover, the process of data query and combination is close to the ER model, with high reusability of queries and separation of query and modification.

3-5 times the development efficiency is based on reasonable, ER-oriented design of pydantic classes and DataLoader, which are effectively reused and combined.

50% reduction in code volume is due to inheritance and saving traversal logic, as well as the code volume of automatically generated frontend sdk.