"""
Dynamic Pydantic model builder based on GraphQL field selection.
"""

from pydantic import ConfigDict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, get_type_hints, get_origin, get_args, Annotated
from pydantic import BaseModel, create_model, Field
from pydantic.functional_serializers import PlainSerializer
from functools import lru_cache

from pydantic_resolve.constant import ENSURE_SUBSET_REFERENCE, ER_DIAGRAM_PRE_GENERATOR
from pydantic_resolve.utils.er_diagram import ErDiagram, Relationship, AutoLoad
from pydantic_resolve.utils.class_util import safe_issubclass
from pydantic_resolve.utils.types import get_core_types
from pydantic_resolve.graphql.types import FieldSelection
from pydantic_resolve import analysis


def _enum_name_serializer(v):
    """
    Serializer function for enum types to output enum name.

    Args:
        v: Enum value or any other value

    Returns:
        Enum name (e.g., "ADMIN") if enum, otherwise the value unchanged
    """
    if isinstance(v, Enum):
        return v.name
    return v


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
    │   ├── _build_relationship_field()     # Build field with AutoLoad annotation
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

    def __init__(self, er_diagram: ErDiagram, resolver_class: type = None, enable_from_attribute_in_type_adapter: bool = False):
        """
        Args:
            er_diagram: Entity relationship diagram
            resolver_class: Resolver class for cache isolation and pre-analysis.
                           If provided, response models will be pre-analyzed and cached.
            enable_from_attribute_in_type_adapter: Enable Pydantic from_attributes mode.
                           Allows loaders to return Pydantic instances instead of dictionaries.
        """
        self.er_diagram = er_diagram
        self.entity_map = {cfg.kls: cfg for cfg in er_diagram.configs}
        self.resolver_class = resolver_class
        self.enable_from_attribute_in_type_adapter = enable_from_attribute_in_type_adapter
        # Bind lru_cache to instance method
        # This provides LRU eviction + thread safety + instance isolation
        self._build_cached = lru_cache(maxsize=256)(self._build_model_impl)

    def build_response_model(
        self,
        entity: type,
        field_selection: FieldSelection,
        parent_path: str = ""
    ) -> type[BaseModel]:
        """
        Recursively build Pydantic response model (with caching).

        This method checks the cache first and returns cached models when available.
        The cache key is based on entity identity and field selection structure,
        excluding arguments (as they don't affect model structure).

        Args:
            entity: Base entity class
            field_selection: Field selection
            parent_path: Parent path (for debugging)

        Returns:
            Dynamically created Pydantic model class

        Caching Behavior:
        ─────────────────────────────────────────────────────────────────
        - Same query structure with different arguments hits cache:
          { user(id: 1) { name } } and { user(id: 2) { name } }
        - Different query structure misses cache:
          { user { name } } and { user { email } }


             Example Transformation:

        ─────────────────────────────────────────────────────────────────
        GraphQL Query:
            { users { id name posts { title } } }

        Input:
            UserEntity: { id, name, posts: list[PostEntity] }
            FieldSelection: { users: { id, name, posts: { title } } }

        Process:
            1. UserEntity → UserResponse (id, name, posts)
            2. posts field triggers recursive call
            3. PostEntity → PostResponse (title)
            4. Inject AutoLoad annotation for relationship resolution

        Output (dynamic models):
            class PostResponse(BaseModel):
                title: str

            class UserResponse(BaseModel):
                id: int
                name: str
                posts: Annotated[List[PostResponse], AutoLoad()] = []

        Key Implementation Details:
        ─────────────────────────────────────────────────────────────────
        1. Model Name Uniqueness:
           - Uses id(field_selection) suffix: "UserResponse_4302384832"
           - Prevents conflicts when same entity queried with different fields
           - Example: { userA: user { id }, userB: user { name } }
                     → UserResponse_4302384832 vs UserResponse_4302384987

        2. ENSURE_SUBSET_REFERENCE:
           - Dynamic model sets __pydantic_resolve_subset__ = original entity
           - Allows ErLoaderPreGenerator.prepare() to find entity config
           - Required for AutoLoad annotation to resolve correct loader
        ─────────────────────────────────────────────────────────────────
        """
        return self._build_cached(entity, field_selection, parent_path)

    def _build_model_impl(
        self,
        entity: type,
        field_selection: FieldSelection,
        parent_path: str
    ) -> type[BaseModel]:
        """
        Core model building logic (cached by lru_cache).

        Args:
            entity: Base entity class
            field_selection: Field selection (must be hashable)
            parent_path: Parent path

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

        # Step 2: Auto-include foreign key fields (for AutoLoad)
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

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:  field_type = str, selection.alias = None
        Output: (str, ...)

        Input:  field_type = Optional[str], selection.alias = "userName"
        Output: (Optional[str], Field(serialization_alias="userName"))

        Input:  field_type = list[PostEntity], selection.sub_fields = {title, content}
        Output: (List[PostResponse_123], [])  # recursive call to build nested model
        ─────────────────────────────────────────────────────────────────
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

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:  field_type = list[PostEntity], selection.sub_fields = {title}
        Process:
            1. get_core_types() extracts [PostEntity]
            2. PostEntity is BaseModel subclass → recursive build
            3. _build_nested_type() wraps with List[]
        Output: (List[PostResponse_123], [])

        Input:  field_type = str, selection.sub_fields = None
        Output: None  # not a Pydantic model, fallback to scalar
        ─────────────────────────────────────────────────────────────────
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
        """
        Build type tuple for nested model based on container type.

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:  field_type = list[PostEntity], nested_model = PostResponse
        Output: (List[PostResponse], [])

        Input:  field_type = Optional[UserEntity], nested_model = UserResponse
        Output: (Optional[UserResponse], None)

        Input:  field_type = UserEntity (plain), nested_model = UserResponse
        Output: (UserResponse, ...)  # required field
        ─────────────────────────────────────────────────────────────────
        """
        origin = get_origin(field_type)
        args = get_args(field_type)

        # Case 1: List container
        if origin is list:
            return (List[nested_model], [])

        # Case 2: Optional (Union[X, None])
        if origin is Union and type(None) in args:
            return (Optional[nested_model], None)

        # Case 3: Plain required type
        return (nested_model, ...)

    def _apply_alias(
        self,
        type_default: Tuple[type, Any],
        alias: Optional[str]
    ) -> Tuple[type, Any]:
        """
        Apply serialization alias to field definition if present.

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:  type_default = (str, ...), alias = None
        Output: (str, ...)

        Input:  type_default = (str, ...), alias = "userName"
        Output: (str, Field(serialization_alias="userName", default=...))
        ─────────────────────────────────────────────────────────────────
        """
        if alias is None:
            return type_default

        field_type, default = type_default
        return (field_type, Field(serialization_alias=alias, default=default))

    def _build_scalar_field(
        self,
        field_type: type,
        alias: Optional[str]
    ) -> Tuple[type, Any]:
        """
        Build field definition for scalar types.

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:  field_type = int, alias = None
        Output: (int, ...)  # ... means required field

        Input:  field_type = str, alias = "id"
        Output: (str, Field(serialization_alias="id"))

        Input:  field_type = UserRole (Enum), alias = None
        Output: (Annotated[UserRole, PlainSerializer(_enum_name_serializer)], ...)
        ─────────────────────────────────────────────────────────────────
        """
        # Check if field type is an Enum - use PlainSerializer for GraphQL convention
        core_types = get_core_types(field_type)
        for core_type in core_types:
            if safe_issubclass(core_type, Enum):
                # Wrap enum type with PlainSerializer to output enum.name
                serialized_type = Annotated[field_type, PlainSerializer(_enum_name_serializer)]
                if alias:
                    return (serialized_type, Field(serialization_alias=alias))
                return (serialized_type, ...)

        # Non-enum scalar field
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
        """
        Add required foreign key fields to field definitions.

        Example:
        ─────────────────────────────────────────────────────────────────
        Scenario: UserEntity has Relationship(fk='id', target=PostEntity, name='posts')
                  Query selects 'posts' field which needs 'id' for AutoLoad

        Before:
            field_definitions = {'name': (str, ...)}

        After:
            field_definitions = {'name': (str, ...), 'id': (int, ...)}

        Why: AutoLoad() needs the FK field to fetch related posts
        ─────────────────────────────────────────────────────────────────
        """
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
        """
        Add relationship fields based on ERD configuration.

        Example:
        ─────────────────────────────────────────────────────────────────
        Scenario: UserEntity.__relationships__ = [
            Relationship(fk='id', target=list[PostEntity], name='posts', loader=post_loader)
        ]
        Query: { users { id posts { title } } }

        Process:
            1. 'posts' not in field_definitions (not a direct field)
            2. _find_relationship('posts') finds the Relationship
            3. _build_relationship_field() creates AutoLoad annotation

        Result:
            field_definitions['posts'] = (
                Annotated[List[PostResponse], AutoLoad()],
                []
            )
        ─────────────────────────────────────────────────────────────────
        """
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
        relationship: Relationship,
        selection: FieldSelection,
        parent_path: str
    ) -> Optional[Tuple[type, Any]]:
        """
        Build field definition for a relationship.

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:
            relationship = Relationship(fk='id', target=list[PostEntity], name='posts')
            selection = {title, content}

        Process:
            1. Extract PostEntity from list[PostEntity]
            2. Recursively build PostResponse model
            3. Wrap with Annotated[..., AutoLoad()]

        Output:
            (Annotated[List[PostResponse], AutoLoad()], [])
        ─────────────────────────────────────────────────────────────────
        """
        target_kls = relationship.target
        origin = get_origin(target_kls)

        # Extract actual entity type
        actual_entity = self._extract_entity_type(target_kls)
        if actual_entity is None:
            return None

        # Recursively build nested model
        nested_model = self.build_response_model(
            actual_entity, selection, parent_path
        )

        # Build annotated type with AutoLoad
        if origin is list:
            base_type = Annotated[List[nested_model], AutoLoad()]
            default = []
        else:
            base_type = Annotated[Optional[nested_model], AutoLoad()]
            default = None

        return self._apply_alias((base_type, default), selection.alias)

    def _extract_entity_type(self, target_kls: type) -> Optional[type]:
        """
        Extract entity type from potentially generic type like list[Entity].

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:  list[PostEntity]
        Output: PostEntity

        Input:  Optional[UserEntity]
        Output: UserEntity

        Input:  CommentEntity
        Output: CommentEntity
        ─────────────────────────────────────────────────────────────────
        """
        origin = get_origin(target_kls)

        if origin is list:
            args = get_args(target_kls)
            return args[0] if args else None

        return target_kls

    # ========== Utility Methods ==========

    def _get_type_hints(self, entity: type) -> Dict[str, type]:
        """
        Safely get type hints for an entity.

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:  UserEntity (with fields: id: int, name: str, posts: list[Post])
        Output: {'id': int, 'name': str, 'posts': list[Post]}

        Input:  Invalid class with forward reference issues
        Output: {}  # graceful fallback
        ─────────────────────────────────────────────────────────────────
        """
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
        """
        Create dynamic Pydantic model with proper configuration.

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:
            entity = UserEntity
            field_selection = FieldSelection with id(field_selection) = 123456789
            field_definitions = {
                'id': (int, ...),
                'name': (str, ...),
                'posts': (Annotated[List[PostResponse], AutoLoad()], [])
            }

        Process:
            1. Generate unique name: "UserEntityResponse_123456789"
            2. Call pydantic.create_model() with field definitions
            3. Set __pydantic_resolve_subset__ = UserEntity
            4. Pre-analyze model if resolver_class is provided

        Output:
            class UserEntityResponse_123456789(BaseModel):
                id: int
                name: str
                posts: Annotated[List[PostResponse], AutoLoad()] = []
                __pydantic_resolve_subset__ = UserEntity
        ─────────────────────────────────────────────────────────────────
        """
        model_name = f"{entity.__name__}Response_{id(field_selection)}"

        # Create model with config to serialize enums as their names (GraphQL convention)
        # Enable from_attributes to allow Pydantic instances as input (for nested relationships)
        config = ConfigDict(
            use_enum_values=False,
            from_attributes=self.enable_from_attribute_in_type_adapter
        )

        dynamic_model = create_model(
            model_name,
            __base__=BaseModel,
            __cls_kwargs__=config,
            **field_definitions
        )

        # Set ENSURE_SUBSET_REFERENCE to point to original entity
        # This allows ErLoaderPreGenerator.prepare() to find original entity config
        setattr(dynamic_model, ENSURE_SUBSET_REFERENCE, entity)

        # Pre-analyze the model if resolver_class is provided
        # This caches metadata early, avoiding repeated analysis in Resolver.resolve()
        if self.resolver_class is not None:
            self._pre_analyze_model(dynamic_model)

        return dynamic_model

    def _pre_analyze_model(self, model: type[BaseModel]) -> None:
        """
        Pre-analyze a response model and cache its metadata.

        This method is called automatically after model creation in _create_model().
        It runs the analysis scan once and caches the result, so that subsequent
        Resolver.resolve() calls can skip the analysis step.

        Args:
            model: The dynamically built response model to analyze
        """
        from pydantic_resolve.resolver import _get_metadata_from_cache, _set_metadata_to_cache

        resolver_class_id = id(self.resolver_class)

        # Skip if already cached (e.g., nested model already analyzed)
        if _get_metadata_from_cache(resolver_class_id, model) is not None:
            return

        # Get er_pre_generator from resolver_class
        er_pre_generator = getattr(self.resolver_class, ER_DIAGRAM_PRE_GENERATOR, None)

        # Run analysis
        metadata = analysis.convert_metadata_key_as_kls(
            analysis.Analytic(er_pre_generator=er_pre_generator).scan(model)
        )

        # Cache the result
        _set_metadata_to_cache(resolver_class_id, model, metadata)

    # ========== FK Field Detection (with caching) ==========

    def _get_required_fk_fields(self, entity: type, selected_fields: Set[str]) -> Set[str]:
        """
        Determine foreign key fields required by AutoLoad (with caching)

        Args:
            entity: Entity class
            selected_fields: Set of selected field names

        Returns:
            Set of foreign key field names that need to be included

        Example:
        ─────────────────────────────────────────────────────────────────
        Scenario:
            UserEntity.__relationships__ = [
                Relationship(fk='id', target=list[PostEntity], name='posts')
            ]
            Query selects: {'id', 'name', 'posts'}

        Process:
            1. Look up relationships for 'posts' field
            2. Find Relationship with name='posts'
            3. Extract fk='id' (the FK needed for AutoLoad)

        Output: {'id'}
        ─────────────────────────────────────────────────────────────────
        """
        return self._get_required_fk_fields_cached(entity, frozenset(selected_fields))

    @lru_cache(maxsize=128)
    def _get_required_fk_fields_cached(self, entity: type, selected_fields: frozenset) -> Set[str]:
        """
        Determine foreign key fields required by AutoLoad (cached version)

        Args:
            entity: Entity class
            selected_fields: Set of selected field names (frozenset, for caching)

        Returns:
            Set of foreign key field names that need to be included

        Example:
        ─────────────────────────────────────────────────────────────────
        Scenario:
            UserEntity.__relationships__ = [
                Relationship(fk='id', target=list[PostEntity], name='posts')
            ]
            Query selects: {'posts'}

        Process:
            1. Iterate through relationships
            2. Find Relationship with name='posts'
            3. Extract fk='id'

        Output: {'id'}
        ─────────────────────────────────────────────────────────────────
        """
        fk_fields = set()

        entity_cfg = self.entity_map.get(entity)
        if not entity_cfg:
            return fk_fields

        for field_name in selected_fields:
            for rel in entity_cfg.relationships:
                if rel.name == field_name:
                    fk_fields.add(rel.fk)

        return fk_fields

    def _find_relationship(self, entity: type, field_name: str) -> Optional[Relationship]:
        """
        Find relationship for a given field.

        Args:
            entity: Entity class
            field_name: Field name to search for

        Returns:
            Relationship object, or None if not found

        Example:
        ─────────────────────────────────────────────────────────────────
        Input:
            entity = UserEntity
            field_name = 'posts'
            UserEntity.__relationships__ = [
                Relationship(fk='id', target=list[PostEntity], name='posts')
            ]

        Output:
            Relationship(fk='id', target=list[PostEntity], name='posts')
        ─────────────────────────────────────────────────────────────────
        """
        entity_cfg = self.entity_map.get(entity)
        if not entity_cfg:
            return None

        for rel in entity_cfg.relationships:
            if rel.name == field_name:
                return rel

        return None
