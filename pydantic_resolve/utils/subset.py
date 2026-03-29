from typing import Any, Literal, Annotated, Optional, List
from pydantic import BaseModel, create_model, model_validator, Field
import copy
import pydantic_resolve.constant as const
from pydantic_resolve.utils.expose import ExposeAs
from pydantic_resolve.utils.collector import SendTo
from pydantic_resolve.utils.er_diagram import LoadBy


def _resolve_relationships_from_field_names(
    field_names: list[str], parent_kls: type
) -> tuple[dict[str, str], dict[str, tuple[Any, Any]]]:
    """
    Resolve FK fields and LoadBy field types from field_names via global ER diagram.

    For each field_name (e.g. 'author'), look up the corresponding Relationship
    in the global ER diagram for parent_kls.

    Returns:
        Tuple of:
        - field_name -> FK field mapping (e.g. {'author': 'author_id'})
        - field_name -> (target_kls, load_many) for generating LoadBy annotations

    Raises ValueError if no global ER diagram or parent not found.
    """
    from pydantic_resolve.utils.er_diagram import get_global_er_diagram

    try:
        er_diagram = get_global_er_diagram()
    except ValueError:
        raise ValueError(
            'SubsetConfig.related requires a global ER diagram. '
            'Use config_global_resolver(er_diagram=...) before defining the class.'
        )

    entity = None
    for config in er_diagram.configs:
        if config.kls is parent_kls:
            entity = config
            break

    if entity is None:
        raise ValueError(
            f'Parent class "{parent_kls.__name__}" not found in ER diagram. '
            f'related requires the parent to be registered in the ER diagram.'
        )

    fk_map: dict[str, str] = {}
    type_map: dict[str, tuple[Any, Any]] = {}

    for rel in entity.relationships:
        if rel.field_name in field_names:
            fk_map[rel.field_name] = rel.field
            type_map[rel.field_name] = (rel.target_kls, rel.load_many)

    # Validate all field_names were found
    not_found = set(field_names) - set(fk_map.keys())
    if not_found:
        for name in sorted(not_found):
            raise ValueError(
                f'Relationship field_name "{name}" not found in '
                f'entity "{parent_kls.__name__}". '
                f'Available: {[r.field_name for r in entity.relationships]}'
            )

    return fk_map, type_map


class SubsetConfig(BaseModel):
    kls: type[BaseModel]  # parent class

    # fields and omit_fields are exclusive
    fields: list[str] | Literal["all"] | None = None
    omit_fields: list[str] | None = None

    # set Field(exclude=True) for these fields
    excluded_fields: list[str] | None = None

    expose_as: list[tuple[str, str]] | None = None
    send_to: list[tuple[str, tuple[str, ...] | str]] | None = None

    # Relationship field_names to auto-resolve FK fields and generate LoadBy annotations
    related: list[str] | None = None

    @model_validator(mode='after')
    def validate_fields(self):
        if self.fields is not None and self.omit_fields is not None:
            raise ValueError("fields and omit_fields are exclusive")

        if self.fields is None and self.omit_fields is None:
            raise ValueError("fields or omit_fields must be provided")
        return self


def _extract_field_infos(kls: type[BaseModel], field_names: list[str]) -> dict[str, Any]:
    field_definitions = {}

    for field_name in field_names:
        field = kls.model_fields.get(field_name)
        if not field:
            raise AttributeError(f'field "{field_name}" does not exist in {kls.__name__}')

        field_definitions[field_name] = (field.annotation, field)

    return field_definitions


def _get_kls_config(kls: type[BaseModel]) -> Any:
    return getattr(kls, 'model_config', None)


def _get_kls_validators(kls: type[BaseModel], field_names: list[str]) -> dict[str, Any]:

    validators = {}
    decorators = getattr(kls, '__pydantic_decorators__', None)

    if decorators and hasattr(decorators, 'field_validators'):
        for validator_name, decorator_info in decorators.field_validators.items():
            # example: @field_validator('email', 'name') -> decorator_info.info.fields = ['email', 'name']
            if any(field in field_names for field in decorator_info.info.fields):
                validators[validator_name] = getattr(kls, validator_name)

    return validators


def _apply_validators(model_class: type[BaseModel], validators: dict[str, Any]) -> None:
    for name, validator in validators.items():
        setattr(model_class, name, validator)


def _extract_extra_fields_from_namespace(namespace: dict[str, Any], disallow: set[str]) -> dict[str, tuple[Any, Any]]:
    """Extract extra field definitions declared on the subset class body.

    Only annotated attributes are considered as Pydantic fields. The result is a
    dict mapping field name -> (annotation, default | Ellipsis) suitable for create_model.

    Args:
        namespace: The class namespace passed into the metaclass with attributes and annotations.
        disallow: Field names that are already selected from the parent and thus cannot be redefined here.

    Raises:
        ValueError: If an extra field duplicates a subset field name.
    """
    annotations: dict[str, Any] = namespace.get('__annotations__', {}) or {}
    extras: dict[str, tuple[Any, Any]] = {}

    for fname, anno in annotations.items():
        if fname in (const.ENSURE_SUBSET_DEFINITION, const.ENSURE_SUBSET_DEFINITION_SHORT):
            continue
        if fname in disallow:
            raise ValueError(f'additional field "{fname}" duplicates subset field')
        default = namespace.get(fname, ...)
        extras[fname] = (anno, default)

    return extras


def _validate_subset_fields(fields: Any):
    if not isinstance(fields, (list, tuple)):
        raise TypeError('fields must be a list or tuple of field names')

    hit = set()
    for f in fields:
        if not isinstance(f, str):
            raise TypeError('each field name must be a string')
        else:
            if f in hit:
                raise ValueError(f'duplicate field name "{f}" in subset fields')
            hit.add(f)


def create_subset(parent: type[BaseModel], fields: list[str], name: str = "SubsetModel") -> type[BaseModel]:
    """
    Create a subset model from a parent BaseModel using Pydantic's create_model.

    Args:
        parent: Parent BaseModel class to create subset from
        fields: List of field names to include in subset
        name: Name of the new subset class (default: "SubsetModel")

    Returns:
        A new BaseModel class containing only the specified fields
    """
    if not issubclass(parent, BaseModel):
        raise TypeError('parent must be a pydantic BaseModel')

    _validate_subset_fields(fields)
    field_infos = _extract_field_infos(parent, fields)
    validators = _get_kls_validators(parent, fields)
    create_model_kwargs = {}

    config = _get_kls_config(parent)
    if config:
        create_model_kwargs['__config__'] = config

    subset_class = create_model(name, **field_infos, **create_model_kwargs)

    _apply_validators(subset_class, validators)
    setattr(subset_class, const.ENSURE_SUBSET_REFERENCE, parent)

    return subset_class


def _build_loadby_annotation(target_kls: Any, load_many: bool):
    """Build Annotated[Optional[target] | List[target], LoadBy()] field annotation."""

    if load_many:
        annotation = Annotated[Optional[List[target_kls]], LoadBy()]
        default = Field(default_factory=list)
    else:
        annotation = Annotated[Optional[target_kls], LoadBy()]
        default = Field(default=None)

    return annotation, default


def _apply_config_modifiers_to_field(
    config: SubsetConfig,
    field_name: str,
    field_default: Any,
) -> Any:
    """Apply SubsetConfig modifiers (excluded_fields, expose_as, send_to) to a single field.

    Only deep-copies when at least one modifier matches. Returns the original
    object unchanged if no modifiers apply.
    """
    result = field_default
    modified = False

    if config.excluded_fields and field_name in config.excluded_fields:
        result = copy.deepcopy(result)
        result.exclude = True
        modified = True

    if config.expose_as:
        for ef_name, alias in config.expose_as:
            if ef_name == field_name:
                if not modified:
                    result = copy.deepcopy(result)
                    modified = True
                result.metadata.append(ExposeAs(alias))

    if config.send_to:
        for sf_name, target in config.send_to:
            if sf_name == field_name:
                if not modified:
                    result = copy.deepcopy(result)
                    modified = True
                result.metadata.append(SendTo(target))

    return result


class SubsetMeta(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        # subset_info is expected to be:
        # - a tuple of (parent_class, list_of_field_names)
        # - a tuple of (parent_class, list_of_field_names, list_of_related_field_names)
        # - a SubsetConfig
        subset_info = namespace.get(const.ENSURE_SUBSET_DEFINITION) or namespace.get(const.ENSURE_SUBSET_DEFINITION_SHORT)

        # Allow defining the base marker class without warning, bypass
        if name == 'DefineSubset' and not bases:
            return super().__new__(cls, name, bases, namespace, **kwargs)

        if not subset_info:
            raise ValueError(f'Class {name} must define {const.ENSURE_SUBSET_DEFINITION} to use SubsetMeta')

        related_field_names: list[str] = []

        if isinstance(subset_info, SubsetConfig):
            parent_kls = subset_info.kls

            if subset_info.fields is not None:
                if subset_info.fields == "all":  # special value to include all fields
                    subset_fields = list(parent_kls.model_fields.keys())
                else:
                    subset_fields = subset_info.fields
            else:
                all_fields = list(parent_kls.model_fields.keys())
                omit_set = set(subset_info.omit_fields)
                subset_fields = [f for f in all_fields if f not in omit_set]

            if subset_info.related:
                related_field_names = subset_info.related
        else:
            parent_kls = subset_info[0]
            subset_fields = subset_info[1]
            if len(subset_info) > 2:
                related_field_names = subset_info[2]

        _validate_subset_fields(subset_fields)
        field_infos = _extract_field_infos(parent_kls, subset_fields)

        if isinstance(subset_info, SubsetConfig):
            for fname, (annotation, field_info) in list(field_infos.items()):
                new_field_info = _apply_config_modifiers_to_field(subset_info, fname, field_info)
                if new_field_info is not field_info:
                    field_infos[fname] = (annotation, new_field_info)

        # Then extract extra fields defined in class body
        extra_fields = _extract_extra_fields_from_namespace(namespace, set(subset_fields))

        # Parent validators and config should still apply to subset fields
        create_model_kwargs: dict[str, Any] = {}
        attributes_to_attach: dict[str, Any] = {}
        methods_to_attach: dict[str, Any] = {}

        validators = _get_kls_validators(parent_kls, subset_fields)
        config = _get_kls_config(parent_kls)
        if config:
            create_model_kwargs['__config__'] = config

        # Use the caller's module for better reprs and pickling
        create_model_kwargs['__module__'] = namespace.get('__module__', __name__)

        for ns_key, ns_value in namespace.items():
            # definition like __pydatnic_resolve_expose__ or __pydantic_resolve_collect__ will be kept, just in case.
            # except __pydantic_resolve_subset__  ( __subset__ will also be ignored)
            if ns_key.startswith('__pydantic_resolve') and ns_key != const.ENSURE_SUBSET_DEFINITION:
                attributes_to_attach[ns_key] = ns_value
                continue

            if callable(ns_value) and (ns_key.startswith(const.RESOLVE_PREFIX) or ns_key.startswith(const.POST_PREFIX)):
                methods_to_attach[ns_key] = ns_value

        field_definitions = {}
        field_definitions.update(field_infos)
        field_definitions.update(extra_fields)

        # Auto-add FK fields and LoadBy fields from related via global ER diagram
        if related_field_names:
            fk_map, type_map = _resolve_relationships_from_field_names(
                related_field_names, parent_kls
            )

            all_defined_fields = set(subset_fields) | set(extra_fields.keys())
            parent_field_names = set(parent_kls.model_fields.keys())

            for field_name, fk_field in fk_map.items():
                # Auto-add FK field with exclude=True if not already defined
                if fk_field not in all_defined_fields:
                    if fk_field in parent_field_names:
                        parent_field = parent_kls.model_fields[fk_field]
                        field_definitions[fk_field] = (parent_field.annotation, Field(default=None, exclude=True))
                    else:
                        raise ValueError(
                            f'Related field_name "{field_name}" resolves to FK field "{fk_field}" '
                            f'which does not exist in parent class "{parent_kls.__name__}". '
                            f'Available fields: {list(parent_field_names)}'
                        )

                # Auto-generate LoadBy field if not already defined in class body
                if field_name not in extra_fields:
                    target_kls, load_many = type_map[field_name]
                    annotation, default = _build_loadby_annotation(target_kls, load_many)

                    # Apply SubsetConfig modifiers to auto-generated LoadBy fields
                    if isinstance(subset_info, SubsetConfig):
                        default = _apply_config_modifiers_to_field(subset_info, field_name, default)

                    field_definitions[field_name] = (annotation, default)

        subset_class = create_model(
            name,
            **field_definitions,
            **create_model_kwargs
        )

        # Apply excluded_fields to auto-generated LoadBy fields after create_model,
        # since create_model does not preserve exclude=True when processing
        # Annotated[..., LoadBy()] annotations.
        if isinstance(subset_info, SubsetConfig) and subset_info.excluded_fields:
            for fname in subset_info.excluded_fields:
                if fname in subset_class.model_fields:
                    subset_class.model_fields[fname].exclude = True
            subset_class.model_rebuild(force=True)

        _apply_validators(subset_class, validators)

        for method_name, method in methods_to_attach.items():
            setattr(subset_class, method_name, method)
        for attr_name, attr_value in attributes_to_attach.items():
            setattr(subset_class, attr_name, attr_value)
        setattr(subset_class, const.ENSURE_SUBSET_REFERENCE, parent_kls)

        return subset_class


class DefineSubset(metaclass=SubsetMeta):
    pass
