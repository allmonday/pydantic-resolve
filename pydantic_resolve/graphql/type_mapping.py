"""
Type mapping utilities for GraphQL.

Provides centralized type conversion between Python and GraphQL types.
"""

from typing import get_origin, get_args, Union
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from pydantic import BaseModel


# Python 基础类型到 GraphQL 类型的映射
PYTHON_TO_GQL_TYPES = {
    int: 'Int',
    str: 'String',
    float: 'Float',
    bool: 'Boolean',
}


def map_python_to_graphql(python_type: type, include_required: bool = True) -> str:
    """
    将 Python 类型映射为 GraphQL 类型字符串

    Args:
        python_type: Python 类型
        include_required: 是否包含 !（表示非空）

    Returns:
        GraphQL 类型字符串（如 "String!", "[Int]!"）

    Examples:
        >>> map_python_to_graphql(int)
        "Int!"
        >>> map_python_to_graphql(list[int])
        "[Int]!"
        >>> map_python_to_graphql(Optional[str])
        "String"
    """
    required_suffix = "!" if include_required else ""

    # 使用 get_core_types 处理所有包装类型
    core_types = get_core_types(python_type)
    if not core_types:
        return "String" + required_suffix  # 默认为 String

    core_type = core_types[0]
    origin = get_origin(python_type)

    # 检查是否是 list 类型
    is_list = origin is list or (
        hasattr(python_type, '__origin__') and
        python_type.__origin__ is list
    )

    if is_list:
        # list[T] -> [T!]!
        inner_gql = map_python_to_graphql(core_type, include_required=True)
        return f"[{inner_gql}]{required_suffix}"
    else:
        # T -> T!
        if safe_issubclass(core_type, BaseModel):
            return f"{core_type.__name__}{required_suffix}"
        else:
            # 标量类型
            scalar_name = map_scalar_type(core_type)
            return f"{scalar_name}{required_suffix}"


def map_scalar_type(python_type: type) -> str:
    """
    将 Python 标量类型映射为 GraphQL 标量类型名

    Args:
        python_type: Python 类型

    Returns:
        GraphQL 标量类型名（"Int", "String", "Boolean", "Float"）

    Examples:
        >>> map_scalar_type(int)
        "Int"
        >>> map_scalar_type(str)
        "String"
    """
    # 检查直接映射
    if python_type in PYTHON_TO_GQL_TYPES:
        return PYTHON_TO_GQL_TYPES[python_type]

    # 通过字符串检查（处理类型字符串等情况）
    type_str = str(python_type).lower()
    if "int" in type_str:
        return "Int"
    elif "bool" in type_str:
        return "Boolean"
    elif "float" in type_str:
        return "Float"
    else:
        return "String"


def get_graphql_type_description(gql_type: str) -> str:
    """
    获取 GraphQL 标量类型的描述

    Args:
        gql_type: GraphQL 类型名

    Returns:
        类型描述字符串
    """
    descriptions = {
        "Int": "The `Int` scalar type represents non-fractional signed whole numeric values.",
        "Float": "The `Float` scalar type represents signed double-precision fractional values.",
        "String": "The `String` scalar type represents textual data.",
        "Boolean": "The `Boolean` scalar type represents `true` or `false`.",
        "ID": "The `ID` scalar type represents a unique identifier.",
    }
    return descriptions.get(gql_type)


def is_union_type(type_hint: type) -> bool:
    """
    检查类型是否是 Union（包括 Optional）

    Args:
        type_hint: 类型提示

    Returns:
        是否是 Union 类型
    """
    origin = get_origin(type_hint)
    return origin is Union


def is_list_type(type_hint: type) -> bool:
    """
    检查类型是否是 list

    Args:
        type_hint: 类型提示

    Returns:
        是否是 list 类型
    """
    origin = get_origin(type_hint)
    return origin is list


def unwrap_optional(type_hint: type):
    """
    从 Optional[T] 或 Union[T, None] 中提取 T

    Args:
        type_hint: 类型提示

    Returns:
        如果是 Optional[T]，返回 T
        否则返回原类型

    Examples:
        >>> unwrap_optional(Optional[int])
        int
        >>> unwrap_optional(int)
        int
    """
    core_types = get_core_types(type_hint)
    # 过滤掉 NoneType
    non_none_types = [t for t in core_types if t is not type(None)]
    return non_none_types[0] if non_none_types else type_hint


def extract_list_element_type(list_type: type):
    """
    从 list[T] 中提取元素类型 T

    Args:
        list_type: 列表类型

    Returns:
        元素类型，如果不是 list 则返回 None

    Examples:
        >>> extract_list_element_type(list[int])
        int
    """
    if not is_list_type(list_type):
        return None

    args = get_args(list_type)
    if args:
        return args[0]
    return None
