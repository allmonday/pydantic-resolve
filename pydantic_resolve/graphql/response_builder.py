"""
Dynamic Pydantic model builder based on GraphQL field selection.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, get_type_hints, get_origin, get_args, Annotated
from pydantic import BaseModel, create_model, Field
from functools import lru_cache

from ..constant import ENSURE_SUBSET_REFERENCE
from ..utils.er_diagram import ErDiagram, Relationship, MultipleRelationship, LoadBy, ErLoaderPreGenerator
from ..utils.class_util import safe_issubclass
from ..utils.types import get_core_types
from .types import FieldSelection


@dataclass
class RelationshipInfo:
    """统一封装 Relationship 和 Link 的信息"""
    field: str  # FK 字段名
    target_kls: type  # 目标类型
    loader: Callable | None  # 加载器
    biz: str | None = None  # 仅 Link 有
    is_link: bool = False  # 是否为 Link（MultipleRelationship 中的链接）


class ResponseBuilder:
    """Dynamically create Pydantic models based on field selection

    Class Structure:
    ─────────────────────────────────────────────────────────────────
    ResponseBuilder
    ├── build_response_model()              # Main entry (~30 lines)
    │
    ├── [Field Building]
    │   ├── _build_field_definition()       # Build single field definition
    │   ├── _try_build_nested_field()       # Try to build nested Pydantic model
    │   ├── _build_nested_type()            # Build type tuple for nested model
    │   ├── _apply_alias()                  # Apply serialization alias
    │   └── _build_scalar_field()           # Build scalar field definition
    │
    ├── [FK & Relationships]
    │   ├── _add_fk_fields()                # Add foreign key fields
    │   ├── _add_relationship_fields()      # Add relationship fields from ERD
    │   ├── _build_relationship_field()     # Build field with LoadBy annotation
    │   └── _extract_entity_type()          # Extract entity from list[Entity]
    │
    ├── [Utilities]
    │   ├── _get_type_hints()               # Safely get type hints
    │   └── _create_model()                 # Create dynamic Pydantic model
    │
    └── [FK Detection (cached)]
        ├── _get_required_fk_fields()       # Public wrapper
        ├── _get_required_fk_fields_cached() # LRU cached implementation
        └── _find_relationship()            # Find relationship by field name
    ─────────────────────────────────────────────────────────────────
    """

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
        field_definitions: Dict[str, Tuple[type, Any]] = {}
        type_hints = self._get_type_hints(entity)
        entity_cfg = self.entity_map.get(entity)
        is_registered = entity_cfg is not None

        # Step 1: Process all selected fields
        if field_selection.sub_fields:
            for field_name, selection in field_selection.sub_fields.items():
                if field_name not in type_hints:
                    continue

                # Skip if already processed (relationships handled in Step 3)
                if field_name in field_definitions:
                    continue

                field_def = self._build_field_definition(
                    type_hints[field_name], selection, parent_path
                )
                if field_def:
                    field_definitions[field_name] = field_def

        # Step 2: Auto-include foreign key fields (for LoadBy)
        if is_registered:
            self._add_fk_fields(entity, field_selection, type_hints, field_definitions)

        # Step 3: Process relationship fields (ERD-based)
        if is_registered and field_selection.sub_fields:
            self._add_relationship_fields(
                entity, field_selection, field_definitions, parent_path
            )

        return self._create_model(entity, field_selection, field_definitions)

    # ========== Helper Methods for Field Building ==========

    def _build_field_definition(
        self,
        field_type: type,
        selection: FieldSelection,
        parent_path: str
    ) -> Optional[Tuple[type, Any]]:
        """
        Build a single field definition.

        Returns None if field should be skipped.
        """
        # Handle nested Pydantic models with sub-field selections
        if selection.sub_fields:
            nested_def = self._try_build_nested_field(field_type, selection, parent_path)
            if nested_def is not None:
                return self._apply_alias(nested_def, selection.alias)

        # Handle scalar fields (no sub-fields)
        return self._build_scalar_field(field_type, selection.alias)

    def _try_build_nested_field(
        self,
        field_type: type,
        selection: FieldSelection,
        parent_path: str
    ) -> Optional[Tuple[type, Any]]:
        """
        Try to build nested field definition for Pydantic models.

        Returns None if no nested Pydantic model found.
        """
        core_types = get_core_types(field_type)

        for core_type in core_types:
            if safe_issubclass(core_type, BaseModel):
                nested_model = self.build_response_model(
                    core_type, selection, parent_path
                )
                return self._build_nested_type(field_type, nested_model)

        # No nested Pydantic model found, return None to use scalar logic
        return None

    def _build_nested_type(
        self,
        field_type: type,
        nested_model: type[BaseModel]
    ) -> Tuple[type, Any]:
        """Build type tuple for nested model based on container type."""
        origin = get_origin(field_type)

        if origin is list:
            return (List[nested_model], [])
        else:
            return (Optional[nested_model], None)

    def _apply_alias(
        self,
        type_default: Tuple[type, Any],
        alias: Optional[str]
    ) -> Tuple[type, Any]:
        """Apply serialization alias to field definition if present."""
        if alias is None:
            return type_default

        field_type, default = type_default
        return (field_type, Field(serialization_alias=alias, default=default))

    def _build_scalar_field(
        self,
        field_type: type,
        alias: Optional[str]
    ) -> Tuple[type, Any]:
        """Build field definition for scalar types."""
        if alias:
            return (field_type, Field(serialization_alias=alias))
        return (field_type, ...)

    # ========== Helper Methods for FK and Relationships ==========

    def _add_fk_fields(
        self,
        entity: type,
        field_selection: FieldSelection,
        type_hints: Dict[str, type],
        field_definitions: Dict[str, Tuple[type, Any]]
    ) -> None:
        """Add required foreign key fields to field definitions."""
        selected_fields = set(field_selection.sub_fields.keys()) if field_selection.sub_fields else set()
        fk_fields = self._get_required_fk_fields(entity, selected_fields)

        for fk_field in fk_fields:
            if fk_field not in field_definitions and fk_field in type_hints:
                field_definitions[fk_field] = (type_hints[fk_field], ...)

    def _add_relationship_fields(
        self,
        entity: type,
        field_selection: FieldSelection,
        field_definitions: Dict[str, Tuple[type, Any]],
        parent_path: str
    ) -> None:
        """Add relationship fields based on ERD configuration."""
        for field_name, selection in field_selection.sub_fields.items():
            # Skip already processed fields
            if field_name in field_definitions:
                continue

            # Skip fields without sub-selections
            if not selection.sub_fields:
                continue

            # Find relationship
            relationship = self._find_relationship(entity, field_name)
            if not relationship:
                continue

            # Build relationship field
            field_def = self._build_relationship_field(relationship, selection, parent_path)
            if field_def:
                field_definitions[field_name] = field_def

    def _build_relationship_field(
        self,
        rel_info: RelationshipInfo,
        selection: FieldSelection,
        parent_path: str
    ) -> Optional[Tuple[type, Any]]:
        """Build field definition for a relationship (supports both Relationship and Link)."""
        target_kls = rel_info.target_kls
        origin = get_origin(target_kls)

        # Extract actual entity type
        actual_entity = self._extract_entity_type(target_kls)
        if actual_entity is None:
            return None

        # Recursively build nested model
        nested_model = self.build_response_model(
            actual_entity, selection, parent_path
        )

        # Build annotated type with LoadBy
        if rel_info.is_link:
            # Link 需要传入 biz 参数
            if origin is list:
                base_type = Annotated[List[nested_model], LoadBy(rel_info.field, biz=rel_info.biz)]
                default = []
            else:
                base_type = Annotated[Optional[nested_model], LoadBy(rel_info.field, biz=rel_info.biz)]
                default = None
        else:
            # Relationship 的现有逻辑
            if origin is list:
                base_type = Annotated[List[nested_model], LoadBy(rel_info.field)]
                default = []
            else:
                base_type = Annotated[Optional[nested_model], LoadBy(rel_info.field)]
                default = None

        return self._apply_alias((base_type, default), selection.alias)

    def _extract_entity_type(self, target_kls: type) -> Optional[type]:
        """Extract entity type from potentially generic type like list[Entity]."""
        origin = get_origin(target_kls)

        if origin is list:
            args = get_args(target_kls)
            return args[0] if args else None

        return target_kls

    # ========== Utility Methods ==========

    def _get_type_hints(self, entity: type) -> Dict[str, type]:
        """Safely get type hints for an entity."""
        try:
            return get_type_hints(entity)
        except Exception:
            return {}

    def _create_model(
        self,
        entity: type,
        field_selection: FieldSelection,
        field_definitions: Dict[str, Tuple[type, Any]]
    ) -> type[BaseModel]:
        """Create dynamic Pydantic model with proper configuration."""
        model_name = f"{entity.__name__}Response_{id(field_selection)}"
        dynamic_model = create_model(
            model_name,
            __base__=BaseModel,
            **field_definitions
        )

        # Set ENSURE_SUBSET_REFERENCE to point to original entity
        # This allows ErLoaderPreGenerator.prepare() to find original entity config
        setattr(dynamic_model, ENSURE_SUBSET_REFERENCE, entity)

        return dynamic_model

    # ========== FK Field Detection (with caching) ==========

    def _get_required_fk_fields(self, entity: type, selected_fields: Set[str]) -> Set[str]:
        """
        Determine foreign key fields required by LoadBy (with caching)

        Args:
            entity: Entity class
            selected_fields: Set of selected field names

        Returns:
            Set of foreign key field names that need to be included
        """
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
                if isinstance(rel, Relationship):
                    if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                        fk_fields.add(rel.field)

                elif isinstance(rel, MultipleRelationship):
                    # 检查 links
                    for link in rel.links:
                        if hasattr(link, 'default_field_name') and link.default_field_name == field_name:
                            fk_fields.add(rel.field)  # 使用 MultipleRelationship 的 field

        return fk_fields

    def _find_relationship(self, entity: type, field_name: str) -> Optional[RelationshipInfo]:
        """
        Find relationship for a given field (supports both Relationship and MultipleRelationship)

        Args:
            entity: Entity class
            field_name: Field name (default_field_name)

        Returns:
            RelationshipInfo object, or None if not found
        """
        entity_cfg = self.entity_map.get(entity)
        if not entity_cfg:
            return None

        for rel in entity_cfg.relationships:
            if isinstance(rel, Relationship):
                if hasattr(rel, 'default_field_name') and rel.default_field_name == field_name:
                    return RelationshipInfo(
                        field=rel.field,
                        target_kls=rel.target_kls,
                        loader=rel.loader,
                        is_link=False
                    )

            elif isinstance(rel, MultipleRelationship):
                # 在 links 中查找
                for link in rel.links:
                    if hasattr(link, 'default_field_name') and link.default_field_name == field_name:
                        return RelationshipInfo(
                            field=rel.field,  # 使用 MultipleRelationship 的 field
                            target_kls=rel.target_kls,  # 使用 MultipleRelationship 的 target_kls
                            loader=link.loader,
                            biz=link.biz,
                            is_link=True
                        )

        return None
