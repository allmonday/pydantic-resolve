from pydantic import BaseModel
from .base import BaseEntity
from pydantic_resolve.utils.er_diagram import Relationship

# Problem: Direct import of UserEntity creates circular dependency
# - post.py imports UserEntity from user.py
# - user.py imports PostEntity from post.py
# - Python cannot resolve this circular import
# This demonstrates why we need string-based references or module path syntax

class PostEntity(BaseModel, BaseEntity):
    __relationships__ = [
        # Direct class reference causes circular import
        Relationship(field='user_id', target_kls='tests.er_diagram.circular.entities.user:UserEntity', loader=None),
    ]

    id: int
    user_id: int
    title: str
