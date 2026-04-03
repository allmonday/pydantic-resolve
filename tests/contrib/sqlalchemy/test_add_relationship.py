from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_resolve import Entity, ErDiagram, MutationConfig, QueryConfig, Relationship


async def _dummy_loader(keys):
    return [None for _ in keys]


class _Post(BaseModel):
    id: int


class _Comment(BaseModel):
    id: int


def test_add_relationship_merges_relationship_query_and_mutation():
    class User(BaseModel):
        id: int

    def list_posts(limit: int = 10):
        return []

    def create_post(title: str):
        return None

    def list_comments(limit: int = 10):
        return []

    def create_comment(content: str):
        return None

    base_diagram = ErDiagram(
        entities=[
            Entity(
                kls=User,
                relationships=[
                    Relationship(
                        fk="id",
                        name="posts",
                        target=list[_Post],
                        loader=_dummy_loader,
                    )
                ],
                queries=[QueryConfig(method=list_posts)],
                mutations=[MutationConfig(method=create_post)],
            )
        ]
    )

    merged = base_diagram.add_relationship(
        [
            Entity(
                kls=User,
                relationships=[
                    Relationship(
                        fk="id",
                        name="comments",
                        target=list[_Comment],
                        loader=_dummy_loader,
                    )
                ],
                queries=[QueryConfig(method=list_comments)],
                mutations=[MutationConfig(method=create_comment)],
            )
        ]
    )

    user_cfg = next(cfg for cfg in merged.entities if cfg.kls is User)

    assert {rel.name for rel in user_cfg.relationships} == {"posts", "comments"}
    assert {q.method.__name__ for q in user_cfg.queries} == {"list_posts", "list_comments"}
    assert {m.method.__name__ for m in user_cfg.mutations} == {"create_post", "create_comment"}


def test_add_relationship_raises_on_duplicate_relationship_name():
    class User(BaseModel):
        id: int

    base_diagram = ErDiagram(
        entities=[
            Entity(
                kls=User,
                relationships=[
                    Relationship(
                        fk="id",
                        name="posts",
                        target=list[_Post],
                        loader=_dummy_loader,
                    )
                ],
            )
        ]
    )

    with pytest.raises(ValueError):
        base_diagram.add_relationship(
            [
                Entity(
                    kls=User,
                    relationships=[
                        Relationship(
                            fk="id",
                            name="posts",
                            target=list[_Comment],
                            loader=_dummy_loader,
                        )
                    ],
                )
            ]
        )


def test_add_relationship_raises_on_duplicate_query_name():
    class User(BaseModel):
        id: int

    def list_items(limit: int = 10):
        return []

    base_diagram = ErDiagram(
        entities=[Entity(kls=User, queries=[QueryConfig(method=list_items)])]
    )

    with pytest.raises(ValueError):
        base_diagram.add_relationship(
            [Entity(kls=User, queries=[QueryConfig(method=list_items)])]
        )


def test_add_relationship_raises_on_duplicate_mutation_name():
    class User(BaseModel):
        id: int

    def create_item(name: str):
        return None

    base_diagram = ErDiagram(
        entities=[Entity(kls=User, mutations=[MutationConfig(method=create_item)])]
    )

    with pytest.raises(ValueError):
        base_diagram.add_relationship(
            [Entity(kls=User, mutations=[MutationConfig(method=create_item)])]
        )


def test_add_relationship_with_empty_entities_returns_equivalent_diagram():
    class User(BaseModel):
        id: int

    base_diagram = ErDiagram(
        entities=[
            Entity(
                kls=User,
                relationships=[
                    Relationship(
                        fk="id",
                        name="posts",
                        target=list[_Post],
                        loader=_dummy_loader,
                    )
                ],
            )
        ],
        description="demo",
    )

    merged = base_diagram.add_relationship([])

    assert merged == base_diagram
    assert merged is not base_diagram


def test_add_relationship_raises_on_duplicate_incoming_kls():
    class User(BaseModel):
        id: int

    base_diagram = ErDiagram(entities=[])

    incoming = [
        Entity(
            kls=User,
            relationships=[
                Relationship(
                    fk="id",
                    name="posts",
                    target=list[_Post],
                    loader=_dummy_loader,
                )
            ],
        ),
        Entity(
            kls=User,
            relationships=[
                Relationship(
                    fk="id",
                    name="comments",
                    target=list[_Comment],
                    loader=_dummy_loader,
                )
            ],
        ),
    ]

    with pytest.raises(ValueError, match="Duplicate incoming entity.kls detected"):
        base_diagram.add_relationship(incoming)
