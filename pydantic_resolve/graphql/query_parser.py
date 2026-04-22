"""
GraphQL query parser using graphql-core.
"""

from typing import Any, Optional
from graphql import parse as parse_graphql
from graphql.language.ast import (
    ArgumentNode,
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)

from pydantic_resolve.graphql.types import FieldSelection, ParsedQuery
from pydantic_resolve.graphql.exceptions import QueryParseError


class QueryParser:
    """Parse GraphQL queries and extract field selection trees"""

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

        # Extract fragment definitions for spread expansion
        fragments = self._extract_fragments(document)

        # Extract all root query fields (supports multiple, including fragments)
        root_fields = self._extract_root_fields(operation, fragments)
        if not root_fields:
            raise QueryParseError("Query is empty")

        # Build field selection trees for all root fields
        field_tree = {}
        for root_field in root_fields:
            root_field_name = root_field.name.value
            parsed_field = self._build_field_tree(root_field, fragments)
            if root_field_name in field_tree:
                field_tree[root_field_name] = self._merge_field_selections(
                    field_tree[root_field_name],
                    parsed_field,
                )
            else:
                field_tree[root_field_name] = parsed_field

        return ParsedQuery(
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

    def _extract_fragments(
        self,
        document: DocumentNode,
    ) -> dict[str, FragmentDefinitionNode]:
        """Extract named fragment definitions from document."""
        fragments: dict[str, FragmentDefinitionNode] = {}
        for definition in document.definitions:
            if isinstance(definition, FragmentDefinitionNode):
                fragments[definition.name.value] = definition
        return fragments

    def _extract_root_fields(
        self,
        operation: OperationDefinitionNode,
        fragments: Optional[dict[str, FragmentDefinitionNode]] = None,
    ) -> list[FieldNode]:
        """Extract all root query fields"""
        selection_set = operation.selection_set
        if not selection_set or not selection_set.selections:
            raise QueryParseError("Query is empty")

        return self._extract_fields_from_selection_set(selection_set, fragments or {})

    def _extract_fields_from_selection_set(
        self,
        selection_set: SelectionSetNode,
        fragments: dict[str, FragmentDefinitionNode],
    ) -> list[FieldNode]:
        """Flatten FieldNodes from selection set, expanding fragments recursively."""
        fields: list[FieldNode] = []

        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                fields.append(selection)
            elif isinstance(selection, FragmentSpreadNode):
                fragment_name = selection.name.value
                fragment = fragments.get(fragment_name)
                if fragment is None:
                    raise QueryParseError(f"Unknown fragment: {fragment_name}")
                fields.extend(self._extract_fields_from_selection_set(fragment.selection_set, fragments))
            elif isinstance(selection, InlineFragmentNode):
                fields.extend(self._extract_fields_from_selection_set(selection.selection_set, fragments))

        return fields

    def _build_field_tree(
        self,
        field_node: FieldNode,
        fragments: Optional[dict[str, FragmentDefinitionNode]] = None,
    ) -> FieldSelection:
        """Recursively build field selection tree"""
        fragments = fragments or {}

        # Reject aliases — not supported in this version
        if field_node.alias:
            raise QueryParseError(
                f"Field aliases are not supported: '{field_node.alias.value}' on '{field_node.name.value}'. "
                "Use the original field name."
            )

        # Extract arguments
        arguments = self._extract_arguments(field_node)

        # Recursively process nested fields
        sub_fields = None
        if field_node.selection_set:
            sub_fields = {}
            for selection in field_node.selection_set.selections:
                if isinstance(selection, FieldNode):
                    sub_field_name = selection.name.value
                    parsed_field = self._build_field_tree(selection, fragments)
                    if sub_field_name in sub_fields:
                        sub_fields[sub_field_name] = self._merge_field_selections(
                            sub_fields[sub_field_name],
                            parsed_field,
                        )
                    else:
                        sub_fields[sub_field_name] = parsed_field
                elif isinstance(selection, FragmentSpreadNode):
                    fragment_name = selection.name.value
                    fragment = fragments.get(fragment_name)
                    if fragment is None:
                        raise QueryParseError(f"Unknown fragment: {fragment_name}")

                    for fragment_field in self._extract_fields_from_selection_set(fragment.selection_set, fragments):
                        sub_field_name = fragment_field.name.value
                        parsed_field = self._build_field_tree(fragment_field, fragments)
                        if sub_field_name in sub_fields:
                            sub_fields[sub_field_name] = self._merge_field_selections(
                                sub_fields[sub_field_name],
                                parsed_field,
                            )
                        else:
                            sub_fields[sub_field_name] = parsed_field
                elif isinstance(selection, InlineFragmentNode):
                    for inline_field in self._extract_fields_from_selection_set(selection.selection_set, fragments):
                        sub_field_name = inline_field.name.value
                        parsed_field = self._build_field_tree(inline_field, fragments)
                        if sub_field_name in sub_fields:
                            sub_fields[sub_field_name] = self._merge_field_selections(
                                sub_fields[sub_field_name],
                                parsed_field,
                            )
                        else:
                            sub_fields[sub_field_name] = parsed_field

        return FieldSelection(
            sub_fields=sub_fields,
            arguments=arguments
        )

    def _extract_arguments(self, field_node: FieldNode) -> dict[str, Any]:
        """Extract field arguments"""
        arguments = {}
        if field_node.arguments:
            for arg in field_node.arguments:
                if isinstance(arg, ArgumentNode):
                    # Get argument value
                    value = self._get_argument_value(arg.value)
                    arguments[arg.name.value] = value
        return arguments

    def _get_argument_value(self, value_node) -> Any:
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
        # Variable
        elif kind == 'variable':
            variable_name = getattr(getattr(value_node, 'name', None), 'value', '<unknown>')
            raise QueryParseError(
                f"GraphQL variables are not supported yet: ${variable_name}. "
                "Please use inline argument values."
            )
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

    def _merge_field_selections(
        self,
        left: FieldSelection,
        right: FieldSelection,
    ) -> FieldSelection:
        """Merge two selections for the same field name."""
        merged_arguments = None
        if left.arguments or right.arguments:
            merged_arguments = {
                **(left.arguments or {}),
                **(right.arguments or {}),
            }

        merged_sub_fields = None
        if left.sub_fields or right.sub_fields:
            merged_sub_fields = dict(left.sub_fields or {})
            for field_name, sub_selection in (right.sub_fields or {}).items():
                if field_name in merged_sub_fields:
                    merged_sub_fields[field_name] = self._merge_field_selections(
                        merged_sub_fields[field_name],
                        sub_selection,
                    )
                else:
                    merged_sub_fields[field_name] = sub_selection

        return FieldSelection(
            sub_fields=merged_sub_fields,
            arguments=merged_arguments,
        )
