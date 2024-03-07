# Comparison with Common Solutions

## Comparison with GraphQL

1. The advantages of GraphQL are 1. convenient for building nested structures, 2. clients can easily generate query subsets. It is very suitable for building public APIs that meet flexible changes.
2. However, many actual businesses in the frontend actually just follow the requirements (fetch the whole set) without the need for flexible selection. The convenience brought by GraphQL is more reflected in the flexible construction of nested structures.
3. GraphQL requires the client to maintain the query statement. Compared with the method of seamless connection between the frontend and backend through openapi.json and tool-generated clients, maintaining these query statements in the frontend and backend integrated architecture is repetitive work.
4. In order to meet the needs of access control, defining APIs one by one through RESTful is more clear and direct than controlling everything through a global Query and Mutation.
5. Pydantic-resolve just meets the need for flexible construction of nested structures. It does not need to introduce a series of concepts and settings like GraphQL. It is very lightweight and non-intrusive. All functions can be achieved by simply resolving.
6. Pydantic-resolve can hide the initialization logic of Dataloader while keeping it lightweight, avoiding the trouble of maintaining Dataloader in multiple places in GraphQL.
7. Pydantic-resolve also provides support for global loader filters, which can simplify a lot of code in some business logic. If the keys of Dataloader are considered equivalent to the join on conditions of relationship, then loader_params is similar to other filtering conditions elsewhere.

> Conclusion:
> 1. GraphQL is more suitable for public APIs.
> 2. For projects where the frontend and backend are treated as a whole, RESTful + Pydantic-resolve is the best way to quickly and flexibly provide data structures.

## Comparison with ORM Relationship

1. Relationship provides ORM-level nested query implementation, but it defaults to using lazy select, which will cause many query times, and when used asynchronously, you need to manually declare code such as `.option(subquery(Model.field))`.
2. The foreign key of the relationship determines that no additional filtering conditions can be provided during the associated query (even if it can, it is a costly approach).
3. The biggest problem with relationship is that it makes the ORM Model and schema code coupled. The nested query that schema wants to do will invade the ORM Model layer.
4. Pydantic-resolve does not have this problem. No relationship needs to be defined at the ORM layer, and all join logic is solved through dataloader batch queries. And through the global loader_params parameter, additional global filtering conditions can be provided.

> Conclusion:
> 1. The flexibility of the relationship solution is low, and it is not easy to modify. The default usage will produce foreign key constraints. It is not friendly to projects with frequent iterations.
> 2. Pydantic-resolve is completely decoupled from the ORM layer and can meet various needs by flexibly creating Dataloader.