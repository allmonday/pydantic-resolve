"""
测试 ResponseBuilder
"""

from typing import Optional, get_origin, get_args
from pydantic import BaseModel
from pydantic_resolve import base_entity
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
