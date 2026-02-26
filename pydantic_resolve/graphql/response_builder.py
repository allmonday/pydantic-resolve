"""
Dynamic Pydantic model builder based on GraphQL field selection.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, get_type_hints, get_origin, get_args, Annotated
from pydantic import BaseModel, create_model, Field
from functools import lru_cache

from ..constant import ENSURE_SUBSET_REFERENCE
from ..utils.er_diagram import ErDiagram, Relationship, LoadBy, ErLoaderPreGenerator
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .types import FieldSelection


class ResponseBuilder:
    """Dynamically create Pydantic models based on field selection"""

    def __init__(self, er_diagram: ErDiagram):
        """
        Args:
            er_diagram: Entity relationship diagram
        """
        self.er_diagram = er_diagram
        self.entity_map = {cfg.kls: cfg for cfg in er_diagram.configs}
        self.loader_pre_generator = ErLoaderPreGenerator(er_diagram)

    def build_response_model(
        self,
        entity: type,
        field_selection: FieldSelection,
        parent_path: str = ""
    ) -> type[BaseModel]:
        """
        Recursively build Pydantic response model

        Args:
            entity: Base entity class
            field_selection: Field selection
            parent_path: Parent path (for debugging)

        Returns:
            Dynamically created Pydantic model class
        """
        # Get entity configuration (may or may not be in ERD)
        entity_cfg = self.entity_map.get(entity)
        is_registered = entity_cfg is not None

        # 1. Collect field definitions
        field_definitions: Dict[str, Tuple[type, Any]] = {}

        # Get all type hints for the entity
        try:
            type_hints = get_type_hints(entity)
        except Exception:
            type_hints = {}

        # 2. Process scalar fields selected in the query
        if field_selection.sub_fields:
            for field_name, selection in field_selection.sub_fields.items():
                if field_name in type_hints:
                    field_type = type_hints[field_name]

                    # Check if it's a nested Pydantic model (list[Entity] or Entity)
                    # and query contains sub-field selections
                    if selection.sub_fields:
                        # Use get_core_types to handle all wrapper types
                        core_types = get_core_types(field_type)

                        for core_type in core_types:
                            # Check if core type is Pydantic BaseModel
                            if safe_issubclass(core_type, BaseModel):
                                origin = get_origin(field_type)

                                # Handle list[Entity] type
                                if origin is list:
                                    # Recursively build nested model
                                    nested_model = self.build_response_model(
                                        core_type,
                                        selection,
                                        f"{parent_path}.{field_name}"
                                    )
                                    if selection.alias:
                                        field_definitions[field_name] = (List[nested_model], Field(serialization_alias=selection.alias, default=[]))
                                    else:
                                        field_definitions[field_name] = (List[nested_model], [])
                                else:
                                    # Handle Entity type (single object)
                                    nested_model = self.build_response_model(
                                        core_type,
                                        selection,
                                        f"{parent_path}.{field_name}"
                                    )
                                    if selection.alias:
                                        field_definitions[field_name] = (Optional[nested_model], Field(serialization_alias=selection.alias, default=None))
                                    else:
                                        field_definitions[field_name] = (Optional[nested_model], None)

                                # Processed, break loop
                                break
                        else:
                            # No nested Pydantic model found, use default logic
                            if selection.alias:
                                field_definitions[field_name] = (field_type, Field(serialization_alias=selection.alias))
                            else:
                                field_definitions[field_name] = (field_type, ...)
                        continue  # Processed, skip subsequent logic

                    # If alias exists, use serialization_alias, keep field name unchanged
                    if selection.alias:
                        field_definitions[field_name] = (field_type, Field(serialization_alias=selection.alias))
                    else:
                        field_definitions[field_name] = (field_type, ...)

        # 3. Auto-include foreign key fields (for LoadBy) - only for entities registered in ERD
        if is_registered:
            fk_fields = self._get_required_fk_fields(
                entity,
                set(field_selection.sub_fields.keys()) if field_selection.sub_fields else set()
            )
            for fk_field in fk_fields:
                if fk_field not in field_definitions and fk_field in type_hints:
                    field_definitions[fk_field] = (type_hints[fk_field], ...)

        # 4. Process nested object fields (relationships) - only for entities registered in ERD
        if is_registered and field_selection.sub_fields:
            for field_name, selection in field_selection.sub_fields.items():
                # Skip already processed fields (nested models handled in step 2)
                if field_name in field_definitions:
                    continue

                if not selection.sub_fields:
                    continue

                # Find relationship
                relationship = self._find_relationship(entity, field_name)
                if not relationship:
                    continue

                # Extract actual entity type (handle list[T])
                target_kls = relationship.target_kls
                origin = get_origin(target_kls)

                if origin is list:
                    # list[PostEntity] -> extract PostEntity
                    args = get_args(target_kls)
                    if args:
                        actual_entity = args[0]
                    else:
                        continue  # Cannot determine element type, skip
                else:
                    actual_entity = target_kls

                # Recursively build nested model (unified build, avoid duplication)
                nested_model = self.build_response_model(
                    actual_entity,
                    selection,
                    f"{parent_path}.{field_name}"
                )

                # Determine field type based on target_kls original type
                if origin is list:
                    # target_kls is list[T], one-to-many relationship, field type is List[nested_model]
                    if selection.alias:
                        field_definitions[field_name] = (Annotated[List[nested_model], LoadBy(relationship.field)], Field(serialization_alias=selection.alias, default=[]))
                    else:
                        field_definitions[field_name] = (Annotated[List[nested_model], LoadBy(relationship.field)], [])
                else:
                    # Many-to-one or one-to-one relationship, field type is Optional[nested_model]
                    if selection.alias:
                        field_definitions[field_name] = (Annotated[Optional[nested_model], LoadBy(relationship.field)], Field(serialization_alias=selection.alias, default=None))
                    else:
                        field_definitions[field_name] = (Annotated[Optional[nested_model], LoadBy(relationship.field)], None)

        # 5. Dynamically create model class
        model_name = f"{entity.__name__}Response_{id(field_selection)}"
        dynamic_model = create_model(
            model_name,
            __base__=BaseModel,
            **field_definitions
        )

        # 6. Set ENSURE_SUBSET_REFERENCE to point to original entity
        # This allows ErLoaderPreGenerator.prepare() to find original entity config via is_compatible_type
        setattr(dynamic_model, ENSURE_SUBSET_REFERENCE, entity)

        return dynamic_model

    def _get_required_fk_fields(self, entity: type, selected_fields: Set[str]) -> Set[str]:
        """
        Determine foreign key fields required by LoadBy (with caching)

        Args:
            entity: Entity class
            selected_fields: Set of selected field names

        Returns:
            Set of foreign key field names that need to be included
        """
        # Use internal method to implement caching (need to convert set to frozenset)
        return self._get_required_fk_fields_cached(entity, frozenset(selected_fields))

    @lru_cache(maxsize=128)
    def _get_required_fk_fields_cached(self, entity: type, selected_fields: frozenset) -> Set[str]:
        """
        Determine foreign key fields required by LoadBy (cached version)

        Args:
            entity: Entity class
            selected_fields: Set of selected field names (frozenset, for caching)

        Returns:
            Set of foreign key field names that need to be included
        """
        fk_fields = set()

        entity_cfg = self.entity_map.get(entity)
        if not entity_cfg:
            return fk_fields

        for field_name in selected_fields:
            for rel in entity_cfg.relationships:
                if not isinstance(rel, Relationship):
                    continue

                # Only check relationships with default_field_name
                if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                    fk_fields.add(rel.field)

        return fk_fields

    def _find_relationship(self, entity: type, field_name: str) -> Optional[Relationship]:
        """
        Find relationship for a given field

        Args:
            entity: Entity class
            field_name: Field name

        Returns:
            Relationship object, or None if not found
        """
        entity_cfg = self.entity_map.get(entity)
        if not entity_cfg:
            return None

        for rel in entity_cfg.relationships:
            if not isinstance(rel, Relationship):
                continue

            # Only match relationships with default_field_name
            if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                return rel

        return None
