import pytest
from typing import List
import pydantic_resolve.constant as const
from pydantic import BaseModel
from pydantic_resolve.utils.resolver_factory import config_resolver
from pydantic_resolve import ErConfig, Relationship
from pydantic_resolve.exceptions import DuplicateErConfigError, DuplicateRelationshipError, InvalidRelationshipError


class User(BaseModel):
    name: str
    def resolve_name(self):
        return self.name + '!!!'

@pytest.mark.asyncio
async def test_resolver_factory():
    MyResolver = config_resolver('MyResolver', [])
    user = User(name='kikodo')
    await MyResolver().resolve(user)
    assert user.name == 'kikodo!!!'

    assert MyResolver.__name__ == 'MyResolver'
    assert getattr(MyResolver, const.ER_DIAGRAM, None) == []


def test_config_resolver_good_case():
    er_configs = [
        ErConfig(
            kls=User,
            relationships=[
                Relationship(field='name', target_kls=List[User], loader=lambda keys: keys),  # type: ignore[list-item]
            ],
        )
    ]
    config_resolver('MyResolver', er_configs)


def test_config_resolver_duplicate_er_config():
    er_configs = [
        ErConfig(kls=User, relationships=[]),
        ErConfig(kls=User, relationships=[]),
    ]

    with pytest.raises(DuplicateErConfigError):
        config_resolver('MyResolver', er_configs)


def test_config_resolver_duplicate_relationship_field():
    er_configs = [
        ErConfig(
            kls=User,
            relationships=[
                Relationship(field='name', target_kls=User, loader=lambda keys: keys),
                Relationship(field='name', target_kls=User, loader=lambda keys: keys),
            ],
        )
    ]

    with pytest.raises(DuplicateRelationshipError):
        config_resolver('MyResolver', er_configs)


def test_config_resolver_invalid_relationship_empty_fields():
    er_configs = [
        ErConfig(
            kls=User,
            relationships=[
                Relationship(field='', target_kls=User, loader=lambda keys: keys),
            ],
        )
    ]

    with pytest.raises(InvalidRelationshipError):
        config_resolver('MyResolver', er_configs)

    er_configs = [
        ErConfig(
            kls=User,
            relationships=[
                Relationship(field='name', target_kls=None, loader=lambda keys: keys),  # type: ignore[arg-type]
            ],
        )
    ]
    with pytest.raises(InvalidRelationshipError):
        config_resolver('MyResolver', er_configs)