# Why Create a New Library?

I am a user of FastAPI (and starlette). Before writing pydantic-resolve, I used two methods to write APIs:

- GraphQL, using a niche python library pygraphy and a mainstream library strawberry-python.
- FastAPI's native restful style interface, paired with SQLAlchemy.

They each have their own advantages and disadvantages.

The combination of GraphQL and pydantic inspired the creation of pydantic-resolve.

## Inspiration from GraphQL

The initial intention of using GraphQL was to provide a flexible backend data interface. Once the Entity and Relationship are clearly defined, GraphQL can provide many general query functions. (Just like there are many tools now that can directly query the db using GraphQL.)

In the early stages of the project, this saved a lot of development time for the backend. Once the relationships between the data were defined, all the object data could be provided to the frontend, allowing the frontend to assemble it themselves. Initially, the cooperation was very pleasant.

But as the project became more complex, the cost of maintaining a layer of data transformation on the frontend began to rise. For example, the frontend might use a roundabout way to query data, such as querying team -> project because the project object did not define a filter by has_team condition. Then the frontend would convert the data into a list of projects. As the number of iterations increased, the frontend began to complain about slow queries. I gradually realized that the claim that GraphQL eliminates the need for frontend-backend communication is an illusion.

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

Another situation is that the backend schema becomes chaotic with iterations. For example, the project will add many associated objects or special calculated values with iterations. But for the query, these pieces of information are not all that should be focused on, and sometimes it is unclear how to write the query.

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

The last straw that broke GraphQL was permission control. Those who have done permission control with GraphQL naturally understand. Anyway, based on node permission control, it is completely unrealistic to implement it. The final compromise is to use the root node of the query to expose different entry points, which is similar to the solution under the restful architecture. entry_1 and entry_2 are isolated, so the flexible query initially envisioned has completely become a series of static schemas.

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
- The graph model in GraphQL, combined with the ER model, can reuse a large number of Entity queries. dataloader can optimize N+1 queries.
- Frontend data combination is a wrong practice. Data combination is also business content, and it can only be maintained for a long time if it is managed uniformly on the business side.
- Frontend querying GraphQL query is also a wrong practice. It will form historical baggage and hinder the backend from refactoring and adjusting the code. In the end, both sides will have dirty code.

## Inspiration from FastAPI and pydantic

After getting in touch with FastAPI and pydantic, what impressed me the most was the ability to generate openapi with the help of pydantic, and then generate the frontend typescript sdk. (Of course, this is not unique to FastAPI)

It directly reduces the cost of frontend-backend docking by an order of magnitude. All backend interface changes can be perceived by the frontend. For example, although GraphQL had many tools to provide type support for queries, it still required writing queries.

After using FastAPI, the frontend became

```python
const projects = await client.BusinessModuleA.getProjects()
```

such a simple and crude query.

The problem that followed was: How to construct a data structure that is friendly to the frontend like GraphQL??

Using SQLAlchemy's relationship can obtain data with a relational structure, but it often requires re-traversing the data to adjust the data and structure.

If the adjustment is written into the query, it will lead to a large number of query statements that cannot be reused.

So it fell into a contradictory state.

The official recommendation is to write a pydantic class (or dataclass) that is very similar to the model definition, and this pydantic object receives the orm query results, similar to the automatic conversion process of `Map<Model, DTO>`.

But if the pydantic class is used as the return type (DTO), it is very likely that the fields will differ from the Model.

At that time, I always felt that this process was a bit awkward. If the data I get is different from what I expect, I have to traverse the data again to make adjustments. For example, after defining Item and Author

```python
class Item(BaseModel):
    id: int
    name: str

class Author(BaseModel):
    id: int
    name: str
    items: List[Item]
```

Item and Author define relationships in Sqlalchemy and can fetch related data at once.

If I need to filter Items based on some complex business logic for business needs, or create a new field in Item based on business logic, I need to expand the loop on the authors and items returned by the ORM query.

```python
for author in authors:
    business_process(author.items)

    for item in author.items:
        another_business_process(item)
        ...
```

It is okay if the number of layers is small. If the content to be modified is large or the number of layers is deep, it will lead to reduced readability and maintainability of similar code.

Inspired by graphene-python, an idea came up, why not define a resolve_method in place?

Then I only need to ensure that the basic fields are consistent with the Model, enjoy the convenience of pydantic automatic mapping, and then use resolve_method to make adjustments in place.

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

So initially, resolve_method was just used to process existing data.

Then I found that resolve_method can be completely asynchronous and used to fetch data. The main thing is to set default values for the target data first, and then return and set the data in the resolve_method.

But starting directly with async will encounter N+1 queries for arrays.

So DataLoader was introduced to solve this problem.

Thus, items became a parameter with a default value of [], and ItemLoader was used to fetch data. This is a mode of loading by declaration.

For scenarios that require flexible combinations, data loading can be driven by class declarations.

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
    async def resolve_items(self, loader=LoaderDepend(ItemLoader)):
        items =  await loader.load(self.id)
        return business_process(items)
```

This means that if I do not mount resolve_items for Author, then ItemLoader will not be driven to execute. Everything is driven by the configuration of the class.

```python
raw_authors = await get_authors()
authors = [Author.model_validate(a) for a in raw_authors]
authors = await Resolver().resolve(authors)
```

I only need to provide the root node data, and pydantic-resolve will automatically decide whether to associate descendant data based on the configuration of Author.

In other words, the external root data and resolve-related code do not need to be adjusted, and the associated configuration parts are centrally maintained inside the pydantic class.

Does it smell like writing a GraphQL query, haha, but it is solidified on the backend.

(btw, I think DataLoader is more convenient than configuring ORM lazy)

Since the fixed pydantic combination has an independent entry, can additional parameters be added to the DataLoader?

Then, since resolve represents fetching data, can a post hook function be added to modify the fetched data after all resolve methods are completed?

So post_methods and post_default_handler were added.

Wait, I can read the variables of the ancestor node with a for loop, how to do it here??

So expose and collector were introduced.

By the time it iterated to this point, it was almost the entire story of pydantic-resolve.

My development mode became:

- First design the business model and define the ER model
- Define models, pydantic classes, and DataLoaders (prepare building blocks)
- Describe the data structure required by the business through inheritance and extension, use DataLoader to fetch data, and use post methods to adjust data (build blocks, make fine adjustments)
- Use FastAPI and TypeScript sdk generator to pass methods and type information to the frontend
- If the business logic changes, adjust or add declared content, and then synchronize the information to the frontend through the sdk

This mode has strong adaptability to the situation of frequent adjustments in the early stage of the business. Adjustments to data relationships only require re-declaring combinations or adding new DataLoaders. (The noise of business-unrelated code is minimized)

And after the project business stabilizes, there is ample space for performance optimization, such as replacing the associated queries of DataLoader with one-time query results, and so on.

In conclusion

3-5 times the development efficiency is the result of reasonable, ER-oriented pydantic classes and DataLoaders being effectively reused and combined.

50% reduction in code volume is due to inheritance and saving traversal logic, as well as the code volume of automatically generating frontend sdk.