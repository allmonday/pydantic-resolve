import pytest
from typing import List
import pydantic_resolve.constant as const
from pydantic import BaseModel
from pydantic_resolve.utils.resolver_configurator import config_resolver
from pydantic_resolve import ErConfig, Relationship


class User(BaseModel):
    name: str
    def resolve_name(self):
        return self.name + '!!!'

class Admin(BaseModel):
    name: str

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


def test_config_resolver_allow_duplicate_field_different_target():
    er_configs = [
        ErConfig(
            kls=User,
            relationships=[
                Relationship(field='name', target_kls=User, loader=lambda keys: keys),
                Relationship(field='name', target_kls=Admin, loader=lambda keys: keys),
            ],
        )
    ]

    # should not raise
    MyResolver = config_resolver('MyResolver', er_configs)
    assert MyResolver is not None