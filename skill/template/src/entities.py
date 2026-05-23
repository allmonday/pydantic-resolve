"""Phase 1: Pydantic Entity DTOs + build_relationship + ErDiagram.
Phase 2: + QueryConfig/MutationConfig bindings.

Entity graph:
    Sprint ──1:N──→ Task ──N:1──→ User
"""
from pydantic import BaseModel, ConfigDict

from pydantic_resolve import ErDiagram, config_resolver
from pydantic_resolve.integration.mapping import Mapping
from pydantic_resolve.integration.sqlalchemy import build_relationship

from src.db import session_factory
from src.models import SprintOrm, TaskOrm, UserOrm


# ── Entity DTOs (from_attributes=True for ORM conversion) ────────────


class UserEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TaskEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    done: bool = False
    sprint_id: int
    owner_id: int | None = None


class SprintEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# ── build_relationship + ErDiagram ───────────────────────────────────

auto_entities = build_relationship(
    mappings=[
        Mapping(entity=UserEntity, orm=UserOrm),
        Mapping(entity=TaskEntity, orm=TaskOrm),
        Mapping(entity=SprintEntity, orm=SprintOrm),
    ],
    session_factory=session_factory,
)


# ── Phase 2: QueryConfig/MutationConfig (added in Phase 2) ───────────

from pydantic_resolve import Entity, MutationConfig, QueryConfig  # noqa: E402

from src.service.sprint.methods import (  # noqa: E402
    create_sprint as _create_sprint,
)
from src.service.sprint.methods import (  # noqa: E402
    get_sprint as _get_sprint,
)
from src.service.sprint.methods import (  # noqa: E402
    list_sprints as _list_sprints,
)
from src.service.task.methods import (  # noqa: E402
    create_task as _create_task,
)
from src.service.task.methods import (  # noqa: E402
    get_tasks_by_sprint as _get_tasks_by_sprint,
)
from src.service.task.methods import (  # noqa: E402
    list_tasks as _list_tasks,
)
from src.service.user.methods import (  # noqa: E402
    list_users as _list_users,
)

query_mutation_entities = [
    Entity(
        kls=SprintEntity,
        queries=[
            QueryConfig(method=_list_sprints, name="sprints"),
            QueryConfig(method=_get_sprint, name="sprint"),
        ],
        mutations=[
            MutationConfig(method=_create_sprint, name="create_sprint"),
        ],
    ),
    Entity(
        kls=TaskEntity,
        queries=[
            QueryConfig(method=_list_tasks, name="tasks"),
            QueryConfig(method=_get_tasks_by_sprint, name="tasks_by_sprint"),
        ],
        mutations=[
            MutationConfig(method=_create_task, name="create_task"),
        ],
    ),
    Entity(
        kls=UserEntity,
        queries=[
            QueryConfig(method=_list_users, name="users"),
        ],
    ),
]

diagram = (
    ErDiagram(entities=[])
    .add_relationship(auto_entities)
    .add_relationship(query_mutation_entities)
)

MyResolver = config_resolver("MyResolver", er_diagram=diagram)
