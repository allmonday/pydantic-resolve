"""
测试 ResponseBuilder
"""

from typing import Optional, get_origin, get_args
from pydantic import BaseModel, ConfigDict
from pydantic_resolve import Relationship, base_entity
from pydantic_resolve.graphql.types import FieldSelection
from pydantic_resolve.graphql.response_builder import ResponseBuilder


class TestBuildNestedType:
    """测试 _build_nested_type 方法"""

    def setup_method(self):
        """设置测试环境"""
        BaseEntity = base_entity()

        class DummyEntity(BaseModel, BaseEntity):
            __relationships__ = []
            id: int

        self.er_diagram = BaseEntity.get_diagram()
        self.builder = ResponseBuilder(self.er_diagram)
        self.nested_model = type('TestResponse', (BaseModel,), {
            '__annotations__': {'id': int},
            'id': 0
        })

    def test_list_type(self):
        """list[Entity] → (List[Response], [])"""
        result = self.builder._build_nested_type(list[BaseModel], self.nested_model)

        assert get_origin(result[0]) is list
        assert result[1] == []

    def test_optional_type(self):
        """Optional[Entity] → (Optional[Response], None)"""
        result = self.builder._build_nested_type(Optional[BaseModel], self.nested_model)

        # Optional is Union[X, None]
        origin = get_origin(result[0])
        args = get_args(result[0])
        assert origin is not None  # It's a Union
        assert type(None) in args
        assert result[1] is None

    def test_plain_required_type(self):
        """Entity → (Response, ...) - required field"""
        result = self.builder._build_nested_type(BaseModel, self.nested_model)

        assert result[0] is self.nested_model
        assert result[1] is ...  # required


def test_dynamic_model_inherits_from_attributes_from_entity_config():
    BaseEntity = base_entity()

    class UserEntity(BaseModel, BaseEntity):
        model_config = ConfigDict(from_attributes=True)
        __relationships__ = []

        id: int
        name: str

    builder = ResponseBuilder(BaseEntity.get_diagram())
    response_model = builder.build_response_model(
        UserEntity,
        FieldSelection(
            sub_fields={
                "id": FieldSelection(),
                "name": FieldSelection(),
            }
        ),
    )

    assert response_model.model_config.get("from_attributes") is True


def test_dynamic_model_enables_from_attributes_via_runtime_flag():
    BaseEntity = base_entity()

    class UserEntity(BaseModel, BaseEntity):
        __relationships__ = []

        id: int

    builder = ResponseBuilder(
        BaseEntity.get_diagram(),
        enable_from_attribute_in_type_adapter=True,
    )
    response_model = builder.build_response_model(
        UserEntity,
        FieldSelection(sub_fields={"id": FieldSelection()}),
    )

    assert response_model.model_config.get("from_attributes") is True


def test_relationship_field_uses_validation_alias_to_avoid_attribute_access():
    BaseEntity = base_entity()

    class PostEntity(BaseModel, BaseEntity):
        __relationships__ = []

        title: str

    class UserEntity(BaseModel, BaseEntity):
        model_config = ConfigDict(from_attributes=True)
        __relationships__ = [
            Relationship(
                fk="id",
                target=list[PostEntity],
                name="posts",
                loader=lambda _: [],
            )
        ]

        id: int

    class UserSource:
        id = 1

        @property
        def posts(self):
            raise AssertionError("posts should not be accessed during model validation")

    builder = ResponseBuilder(BaseEntity.get_diagram())
    response_model = builder.build_response_model(
        UserEntity,
        FieldSelection(
            sub_fields={
                "id": FieldSelection(),
                "posts": FieldSelection(sub_fields={"title": FieldSelection()}),
            }
        ),
    )

    posts_field = response_model.model_fields["posts"]
    assert posts_field.validation_alias == "__pydantic_resolve_skip_posts"

    result = response_model.model_validate(UserSource())
    assert result.id == 1
    # posts is a raw list field (default=[]), not resolved from source
    assert result.posts == []
