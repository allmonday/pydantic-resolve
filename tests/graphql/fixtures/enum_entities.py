"""
Test entities with enum fields for GraphQL enum support tests.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from pydantic_resolve import base_entity, query


# Define enums
class UserRole(Enum):
    """User role enum."""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class PostStatus(Enum):
    """Post status enum."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Priority(int, Enum):
    """Priority enum with int values."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


# Create BaseEntity
BaseEntity = base_entity()


# Define entities with enum fields
class UserWithRoleEntity(BaseModel, BaseEntity):
    """User entity with role enum."""
    __relationships__ = []

    id: int
    name: str
    role: UserRole

    @query(name='usersWithRole')
    async def get_all(cls) -> List['UserWithRoleEntity']:
        """Get all users with roles."""
        return [
            UserWithRoleEntity(id=1, name="Alice", role=UserRole.ADMIN),
            UserWithRoleEntity(id=2, name="Bob", role=UserRole.USER),
        ]


class PostWithStatusEntity(BaseModel, BaseEntity):
    """Post entity with status enum."""
    __relationships__ = []

    id: int
    title: str
    status: PostStatus

    @query(name='postsWithStatus')
    async def get_all(cls) -> List['PostWithStatusEntity']:
        """Get all posts with status."""
        return [
            PostWithStatusEntity(id=1, title="First Post", status=PostStatus.PUBLISHED),
            PostWithStatusEntity(id=2, title="Draft Post", status=PostStatus.DRAFT),
        ]


class TaskWithPriorityEntity(BaseModel, BaseEntity):
    """Task entity with priority enum (IntEnum)."""
    __relationships__ = []

    id: int
    name: str
    priority: Priority

    @query(name='tasksWithPriority')
    async def get_all(cls) -> List['TaskWithPriorityEntity']:
        """Get all tasks with priority."""
        return [
            TaskWithPriorityEntity(id=1, name="Task 1", priority=Priority.HIGH),
            TaskWithPriorityEntity(id=2, name="Task 2", priority=Priority.LOW),
        ]


class ItemWithOptionalStatusEntity(BaseModel, BaseEntity):
    """Item entity with optional status enum."""
    __relationships__ = []

    id: int
    status: Optional[PostStatus] = None

    @query(name='itemsWithOptionalStatus')
    async def get_all(cls) -> List['ItemWithOptionalStatusEntity']:
        """Get all items with optional status."""
        return [
            ItemWithOptionalStatusEntity(id=1, status=PostStatus.PUBLISHED),
            ItemWithOptionalStatusEntity(id=2, status=None),
        ]
