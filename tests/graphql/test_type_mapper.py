"""Tests for ``TypeMapper.collect_referenced_types``.

Direct coverage of the type-walking primitive that UseCase compose,
ErDiagram schema construction, and the ``@serialization`` decorator
all rely on.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import pytest
from pydantic import BaseModel

from pydantic_resolve.graphql.schema.type_mapper import TypeMapper


@pytest.fixture
def mapper() -> TypeMapper:
    return TypeMapper()


# ──────────────────────────────────────────────────
# Test fixtures: DTO + Enum shapes
# ──────────────────────────────────────────────────


class Color(Enum):
    RED = "red"
    GREEN = "green"


class LeafDTO(BaseModel):
    id: int


class MiddleDTO(BaseModel):
    leaf: LeafDTO
    leaves: list[LeafDTO]
    optional_leaf: Optional[LeafDTO] = None


class RootDTO(BaseModel):
    middle: MiddleDTO
    color: Color
    name: str


class SelfRefNode(BaseModel):
    id: int
    children: list["SelfRefNode"] = []


SelfRefNode.model_rebuild()


class DiamondLeafDTO(BaseModel):
    id: int


class DiamondLeftDTO(BaseModel):
    leaf: DiamondLeafDTO


class DiamondRightDTO(BaseModel):
    leaf: DiamondLeafDTO


class DiamondRootDTO(BaseModel):
    left: DiamondLeftDTO
    right: DiamondRightDTO


# ──────────────────────────────────────────────────
# Single BaseModel
# ──────────────────────────────────────────────────


class TestSingleBaseModel:
    def test_returns_input_class_itself(self, mapper):
        result = mapper.collect_referenced_types(LeafDTO)
        assert "LeafDTO" in result
        assert result["LeafDTO"] is LeafDTO

    def test_returns_empty_for_scalar(self, mapper):
        assert mapper.collect_referenced_types(int) == {}
        assert mapper.collect_referenced_types(str) == {}
        assert mapper.collect_referenced_types(None) == {}


# ──────────────────────────────────────────────────
# Nested BaseModels
# ──────────────────────────────────────────────────


class TestNestedBaseModels:
    def test_walks_one_level(self, mapper):
        result = mapper.collect_referenced_types(MiddleDTO)
        assert {"MiddleDTO", "LeafDTO"} <= set(result)

    def test_walks_two_levels(self, mapper):
        result = mapper.collect_referenced_types(RootDTO)
        assert {"RootDTO", "MiddleDTO", "LeafDTO"} <= set(result)

    def test_walks_through_list_field(self, mapper):
        result = mapper.collect_referenced_types(MiddleDTO)
        # ``leaves: list[LeafDTO]`` pulls LeafDTO in transitively
        assert "LeafDTO" in result

    def test_walks_through_optional_field(self, mapper):
        result = mapper.collect_referenced_types(MiddleDTO)
        # ``optional_leaf: Optional[LeafDTO]`` pulls LeafDTO in
        assert "LeafDTO" in result


# ──────────────────────────────────────────────────
# Input annotation shape
# ──────────────────────────────────────────────────


class TestInputAnnotationShape:
    def test_optional_input(self, mapper):
        result = mapper.collect_referenced_types(Optional[LeafDTO])
        assert "LeafDTO" in result

    def test_list_input(self, mapper):
        result = mapper.collect_referenced_types(list[LeafDTO])
        assert "LeafDTO" in result

    def test_optional_list_input(self, mapper):
        result = mapper.collect_referenced_types(Optional[list[LeafDTO]])
        assert "LeafDTO" in result

    def test_dict_input_returns_empty(self, mapper):
        # dict is not a BaseModel/Enum, even with BaseModel values
        result = mapper.collect_referenced_types(dict[str, LeafDTO])
        assert result == {}


# ──────────────────────────────────────────────────
# Enum handling
# ──────────────────────────────────────────────────


class TestEnumHandling:
    def test_includes_top_level_enum_by_default(self, mapper):
        result = mapper.collect_referenced_types(Color)
        assert "Color" in result
        assert result["Color"] is Color

    def test_excludes_top_level_enum_when_disabled(self, mapper):
        result = mapper.collect_referenced_types(Color, include_enums=False)
        assert "Color" not in result

    def test_includes_nested_enum_by_default(self, mapper):
        result = mapper.collect_referenced_types(RootDTO)
        assert "Color" in result

    def test_excludes_nested_enum_when_disabled(self, mapper):
        result = mapper.collect_referenced_types(RootDTO, include_enums=False)
        assert "Color" not in result
        # BaseModels still present
        assert {"RootDTO", "MiddleDTO", "LeafDTO"} <= set(result)


# ──────────────────────────────────────────────────
# Cycles / shared types
# ──────────────────────────────────────────────────


class TestCyclesAndSharedTypes:
    def test_self_reference_terminates(self, mapper):
        result = mapper.collect_referenced_types(SelfRefNode)
        # Should not infinite-loop; SelfRefNode appears once.
        assert list(result.values()).count(SelfRefNode) == 1
        assert "SelfRefNode" in result

    def test_diamond_dependency_dedups(self, mapper):
        result = mapper.collect_referenced_types(DiamondRootDTO)
        # DiamondLeafDTO reachable via both Left and Right, appears once.
        assert list(result.values()).count(DiamondLeafDTO) == 1
        assert {
            "DiamondRootDTO",
            "DiamondLeftDTO",
            "DiamondRightDTO",
            "DiamondLeafDTO",
        } <= set(result)


# ──────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────


class TestEdgeCases:
    def test_skips_unresolved_string_annotation(self, mapper):
        # A pure string annotation can't be resolved to a class — must
        # be skipped silently rather than crashing.
        result = mapper.collect_referenced_types("SomeUnresolvedType")
        assert result == {}

    def test_skips_none_input(self, mapper):
        assert mapper.collect_referenced_types(None) == {}

    def test_returns_dict_keyed_by_class_name(self, mapper):
        result = mapper.collect_referenced_types(RootDTO)
        for name, cls in result.items():
            assert cls.__name__ == name
