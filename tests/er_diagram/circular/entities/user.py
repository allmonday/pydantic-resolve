from pydantic import BaseModel
from .base import BaseEntity
from pydantic_resolve.utils.er_diagram import Relationship

# Problem: Direct import of PostEntity creates circular dependency
# - user.py imports PostEntity from post.py
# - post.py imports UserEntity from user.py
# - Python cannot resolve this circular import
# This demonstrates why we need string-based references or module path syntax

class UserEntity(BaseModel, BaseEntity):
    __relationships__ = [
        # Direct class reference causes circular import
        Relationship(field='id', 
                     target_kls=list['tests.er_diagram.circular.entities.post:PostEntity'], # noqa: F722
                     loader=None),
    ]

    id: int
    name: str
