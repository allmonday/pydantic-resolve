# GraphQL and MCP

[中文版](./graphql_and_mcp.zh.md) | [docs](./index.md)

Once the ERD is in place, GraphQL and MCP become reuse layers. They build on the same model graph instead of asking you to learn a second data-assembly system.

GraphQL and MCP are downstream of the ERD, not an alternative to the Core API.

## GraphQL: Add Root Entry Points to the Same Graph

The relationships from the previous page stay the same. To expose them through GraphQL, you add root queries or mutations.

```python
from pydantic import BaseModel
from pydantic_resolve import GraphQLHandler, Relationship, base_entity, query


BaseEntity = base_entity()


class UserEntity(BaseModel, BaseEntity):
		id: int
		name: str


class TaskEntity(BaseModel, BaseEntity):
		__relationships__ = [
				Relationship(fk='owner_id', target=UserEntity, name='owner', loader=user_loader)
		]
		id: int
		title: str
		owner_id: int


class SprintEntity(BaseModel, BaseEntity):
		__relationships__ = [
				Relationship(fk='id', target=list[TaskEntity], name='tasks', loader=task_loader)
		]
		id: int
		name: str

		@query
		async def get_all(cls, limit: int = 20) -> list['SprintEntity']:
				return await fetch_sprints(limit)


diagram = BaseEntity.get_diagram()
handler = GraphQLHandler(diagram)

result = await handler.execute(
		"""
		{
			sprints {
				id
				name
				tasks {
					id
					title
					owner {
						id
						name
					}
				}
			}
		}
		"""
)
```

### Practical Note

The exact GraphQL root field names come from the generated entity+method naming rule, unless you override the method-name part with `QueryConfig(...)` or `MutationConfig(...)`. The important idea here is not the decorator itself; it is that the nested relationship graph still comes from the same ERD.

If you prefer external configuration instead of decorators, `QueryConfig` and `MutationConfig` can define the same root operations outside the entity classes.

## MCP: Reuse the Same GraphQL Layer for AI Tools

MCP support builds on that GraphQL layer.

```python
from pydantic_resolve import AppConfig, create_mcp_server


mcp = create_mcp_server(
		apps=[AppConfig(name='agile', er_diagram=diagram)]
)
mcp.run()
```

Install the optional dependency if you want MCP support:

```bash
pip install pydantic-resolve[mcp]
```

The main point is architectural reuse:

- the business relationships stay in one ERD
- GraphQL exposes them to structured clients
- MCP exposes them to AI agents and tools

## What This Page Is Not Saying

This page is not suggesting that every user should start with GraphQL or MCP. The Core API remains the best entry point because it teaches the data-assembly model directly.

GraphQL and MCP become compelling only after the ERD is already providing stable relationship knowledge.

## Next

Continue to [Reference Bridge](./reference_bridge.md) for the recommended next reading after the main path ends.