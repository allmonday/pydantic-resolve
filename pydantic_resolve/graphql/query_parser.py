"""
GraphQL query parser using graphql-core.
"""

from typing import Dict
from graphql import parse as parse_graphql
from graphql.language.ast import (
    DocumentNode,
    OperationDefinitionNode,
    FieldNode,
    ArgumentNode,
    OperationType,
)

from ..utils.er_diagram import ErDiagram
from .types import FieldSelection, ParsedQuery
from .exceptions import QueryParseError


class QueryParser:
    """解析 GraphQL 查询并提取字段选择树"""

    def __init__(self, er_diagram: ErDiagram):
        """
        Args:
            er_diagram: 实体关系图
        """
        self.entity_map = {cfg.kls.__name__: cfg.kls for cfg in er_diagram.configs}

    def parse(self, query: str) -> ParsedQuery:
        """
        解析 GraphQL 查询字符串

        Args:
            query: GraphQL 查询字符串

        Returns:
            ParsedQuery 对象，包含解析后的查询信息

        Raises:
            QueryParseError: 当查询解析失败时
        """
        try:
            document = parse_graphql(query)
        except Exception as e:
            raise QueryParseError(f"GraphQL 语法错误: {e}")

        # 提取操作定义（Query）
        operation = self._extract_operation(document)
        if not operation:
            raise QueryParseError("未找到查询操作")

        # 提取所有根查询字段（支持多个）
        root_fields = self._extract_root_fields(operation)
        if not root_fields:
            raise QueryParseError("查询为空")

        # 为所有根字段构建字段选择树
        field_tree = {}
        for root_field in root_fields:
            root_field_name = root_field.name.value
            field_tree[root_field_name] = self._build_field_tree(root_field)

        # 尝试推断第一个实体名称（用于向后兼容，但不验证）
        root_entity = None
        first_field = root_fields[0]
        try:
            first_field_name = first_field.name.value
            root_entity_name = self._infer_entity_from_field(first_field_name)
            if root_entity_name in self.entity_map:
                root_entity = self.entity_map[root_entity_name]
        except QueryParseError:
            # 如果推断失败，让 handler 通过 query_map 来查找
            pass

        return ParsedQuery(
            root_entity=root_entity,
            field_tree=field_tree,
            variables={},
            operation_name=None
        )

    def _extract_operation(self, document: DocumentNode) -> OperationDefinitionNode:
        """提取操作定义（支持 Query 和 Mutation）"""
        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                # 支持 Query 和 Mutation 操作
                if definition.operation in (OperationType.QUERY, OperationType.MUTATION):
                    return definition
        return None

    def _extract_root_fields(self, operation: OperationDefinitionNode) -> list[FieldNode]:
        """提取所有根查询字段"""
        selection_set = operation.selection_set
        if not selection_set or not selection_set.selections:
            raise QueryParseError("查询为空")

        # 返回所有根查询字段
        root_fields = []
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                root_fields.append(selection)

        return root_fields

    def _infer_entity_from_field(self, field_name: str) -> str:
        """
        从字段名推断实体名称

        Examples:
            users -> UserEntity
            user -> UserEntity
            posts -> PostEntity
        """
        # 将字段名转换为 PascalCase
        # users -> Users
        # user -> User
        pascal_name = field_name.capitalize()

        # 尝试匹配实体名称
        if pascal_name + 'Entity' in self.entity_map:
            return pascal_name + 'Entity'

        # 尝试移除尾部的 's'（复数转单数）
        if field_name.endswith('s'):
            singular = field_name[:-1].capitalize()
            if singular + 'Entity' in self.entity_map:
                return singular + 'Entity'

        # 遍历所有实体，查找匹配
        for entity_name in self.entity_map.keys():
            entity_lower = entity_name.lower()
            # 检查是否是单数形式
            if field_name.lower() == entity_lower.replace('entity', ''):
                return entity_name
            # 检查是否是复数形式
            if field_name.lower().endswith('s') and field_name[:-1].lower() == entity_lower.replace('entity', ''):
                return entity_name

        raise QueryParseError(f"无法从字段名 '{field_name}' 推断实体名称")

    def _build_field_tree(self, field_node: FieldNode) -> FieldSelection:
        """递归构建字段选择树"""
        # 提取别名
        alias = field_node.alias.value if field_node.alias else None

        # 提取参数
        arguments = self._extract_arguments(field_node)

        # 递归处理嵌套字段
        sub_fields = None
        if field_node.selection_set:
            sub_fields = {}
            for selection in field_node.selection_set.selections:
                if isinstance(selection, FieldNode):
                    sub_field_name = selection.name.value
                    sub_fields[sub_field_name] = self._build_field_tree(selection)

        return FieldSelection(
            alias=alias,
            sub_fields=sub_fields,
            arguments=arguments
        )

    def _extract_arguments(self, field_node: FieldNode) -> Dict[str, any]:
        """提取字段参数"""
        arguments = {}
        if field_node.arguments:
            for arg in field_node.arguments:
                if isinstance(arg, ArgumentNode):
                    # 获取参数值
                    value = self._get_argument_value(arg.value)
                    arguments[arg.name.value] = value
        return arguments

    def _get_argument_value(self, value_node) -> any:
        """获取参数值（从 GraphQL AST 节点）"""
        # GraphQL AST 中 kind 是字符串，不是枚举
        kind = getattr(value_node, 'kind', '')

        # IntValue
        if kind == 'int_value':
            return int(value_node.value)
        # FloatValue
        elif kind == 'float_value':
            return float(value_node.value)
        # StringValue
        elif kind == 'string_value':
            return value_node.value
        # BooleanValue
        elif kind == 'boolean_value':
            return value_node.value
        # ObjectValue (对象字面量)
        elif kind == 'object_value' and hasattr(value_node, 'fields'):
            obj = {}
            for field in value_node.fields:
                field_name = field.name.value
                obj[field_name] = self._get_argument_value(field.value)
            return obj
        # ListValue
        elif hasattr(value_node, 'values'):
            return [self._get_argument_value(v) for v in value_node.values]
        # 其他类型，尝试获取 value 属性
        elif hasattr(value_node, 'value'):
            return value_node.value
        else:
            return None
