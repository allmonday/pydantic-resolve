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
    """Parse GraphQL queries and extract field selection trees"""

    def __init__(self, er_diagram: ErDiagram):
        """
        Args:
            er_diagram: Entity relationship diagram
        """
        self.entity_map = {cfg.kls.__name__: cfg.kls for cfg in er_diagram.configs}

    def parse(self, query: str) -> ParsedQuery:
        """
        Parse GraphQL query string

        Args:
            query: GraphQL query string

        Returns:
            ParsedQuery object containing parsed query information

        Raises:
            QueryParseError: When query parsing fails
        """
        try:
            document = parse_graphql(query)
        except Exception as e:
            raise QueryParseError(f"GraphQL syntax error: {e}")

        # Extract operation definition (Query)
        operation = self._extract_operation(document)
        if not operation:
            raise QueryParseError("No query operation found")

        # Extract all root query fields (supports multiple)
        root_fields = self._extract_root_fields(operation)
        if not root_fields:
            raise QueryParseError("Query is empty")

        # Build field selection trees for all root fields
        field_tree = {}
        for root_field in root_fields:
            root_field_name = root_field.name.value
            field_tree[root_field_name] = self._build_field_tree(root_field)

        # Try to infer first entity name (for backward compatibility, but don't validate)
        root_entity = None
        first_field = root_fields[0]
        try:
            first_field_name = first_field.name.value
            root_entity_name = self._infer_entity_from_field(first_field_name)
            if root_entity_name in self.entity_map:
                root_entity = self.entity_map[root_entity_name]
        except QueryParseError:
            # If inference fails, let handler find it via query_map
            pass

        return ParsedQuery(
            root_entity=root_entity,
            field_tree=field_tree,
            variables={},
            operation_name=None
        )

    def _extract_operation(self, document: DocumentNode) -> OperationDefinitionNode:
        """Extract operation definition (supports Query and Mutation)"""
        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                # Support Query and Mutation operations
                if definition.operation in (OperationType.QUERY, OperationType.MUTATION):
                    return definition
        return None

    def _extract_root_fields(self, operation: OperationDefinitionNode) -> list[FieldNode]:
        """Extract all root query fields"""
        selection_set = operation.selection_set
        if not selection_set or not selection_set.selections:
            raise QueryParseError("Query is empty")

        # Return all root query fields
        root_fields = []
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                root_fields.append(selection)

        return root_fields

    def _infer_entity_from_field(self, field_name: str) -> str:
        """
        Infer entity name from field name

        Examples:
            users -> UserEntity
            user -> UserEntity
            posts -> PostEntity
        """
        # Convert field name to PascalCase
        # users -> Users
        # user -> User
        pascal_name = field_name.capitalize()

        # Try to match entity name
        if pascal_name + 'Entity' in self.entity_map:
            return pascal_name + 'Entity'

        # Try removing trailing 's' (plural to singular)
        if field_name.endswith('s'):
            singular = field_name[:-1].capitalize()
            if singular + 'Entity' in self.entity_map:
                return singular + 'Entity'

        # Iterate through all entities to find a match
        for entity_name in self.entity_map.keys():
            entity_lower = entity_name.lower()
            # Check if it's singular form
            if field_name.lower() == entity_lower.replace('entity', ''):
                return entity_name
            # Check if it's plural form
            if field_name.lower().endswith('s') and field_name[:-1].lower() == entity_lower.replace('entity', ''):
                return entity_name

        raise QueryParseError(f"Cannot infer entity name from field name '{field_name}'")

    def _build_field_tree(self, field_node: FieldNode) -> FieldSelection:
        """Recursively build field selection tree"""
        # Extract alias
        alias = field_node.alias.value if field_node.alias else None

        # Extract arguments
        arguments = self._extract_arguments(field_node)

        # Recursively process nested fields
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
        """Extract field arguments"""
        arguments = {}
        if field_node.arguments:
            for arg in field_node.arguments:
                if isinstance(arg, ArgumentNode):
                    # Get argument value
                    value = self._get_argument_value(arg.value)
                    arguments[arg.name.value] = value
        return arguments

    def _get_argument_value(self, value_node) -> any:
        """Get argument value from GraphQL AST node"""
        # kind is string in GraphQL AST, not enum
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
        # ObjectValue (object literal)
        elif kind == 'object_value' and hasattr(value_node, 'fields'):
            obj = {}
            for field in value_node.fields:
                field_name = field.name.value
                obj[field_name] = self._get_argument_value(field.value)
            return obj
        # ListValue
        elif hasattr(value_node, 'values'):
            return [self._get_argument_value(v) for v in value_node.values]
        # Other types, try to get value attribute
        elif hasattr(value_node, 'value'):
            return value_node.value
        else:
            return None
