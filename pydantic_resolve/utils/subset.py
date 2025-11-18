from typing import Type, Dict, Any, List, Tuple, Set
from pydantic import BaseModel, create_model
import pydantic_resolve.constant as const


def _extract_field_definitions_for_create_model(parent: Type[BaseModel], field_names: List[str]) -> Dict[str, Tuple]:
    """Extract field definitions in format suitable for create_model (Pydantic v2)."""
    field_definitions = {}
    
    for fname in field_names:
        fld = parent.model_fields.get(fname)
        if not fld:
            raise AttributeError(f'field "{fname}" not existed in {parent.__name__}')
        
        # For create_model, we need (type, default_value) tuple
        if fld.is_required():
            field_definitions[fname] = (fld.annotation, ...)
        else:
            # For non-required fields, just use the default
            field_definitions[fname] = (fld.annotation, fld.default)
    
    return field_definitions


def _get_parent_config(parent: Type[BaseModel]) -> Any:
    """Get parent's configuration (Pydantic v2)."""
    return getattr(parent, 'model_config', None)


def _get_parent_validators(parent: Type[BaseModel], field_names: List[str]) -> Dict[str, Any]:
    """Get parent's validators relevant to the subset fields (Pydantic v2)."""
    validators = {}
    
    # In v2, field validators are stored in __pydantic_decorators__
    decorators = getattr(parent, '__pydantic_decorators__', None)
    if decorators and hasattr(decorators, 'field_validators'):
        for validator_name, decorator_info in decorators.field_validators.items():
            # Check if this validator applies to any of our fields
            validator_fields = decorator_info.info.fields
            if any(field in field_names for field in validator_fields):
                # Copy the validator method
                validators[validator_name] = getattr(parent, validator_name)
    
    return validators


def _apply_validators(model_class: Type[BaseModel], validators: Dict[str, Any]) -> None:
    """Apply validators to Pydantic v2 model after creation."""
    # In v2, validators are handled differently and need to be copied manually
    # This is a simplified approach - the proper way would be to use pydantic's internal mechanisms
    for name, validator in validators.items():
        setattr(model_class, name, validator)


def _extract_extra_fields_from_namespace(namespace: Dict[str, Any], disallow: Set[str]) -> Dict[str, Tuple[Any, Any]]:
    """Extract extra field definitions declared on the subset class body.

    Only annotated attributes are considered as Pydantic fields. The result is a
    dict mapping field name -> (annotation, default | Ellipsis) suitable for create_model.

    Args:
        namespace: The class namespace passed into the metaclass with attributes and annotations.
        disallow: Field names that are already selected from the parent and thus cannot be redefined here.

    Raises:
        ValueError: If an extra field duplicates a subset field name.
    """
    annotations: Dict[str, Any] = namespace.get('__annotations__', {}) or {}
    extras: Dict[str, Tuple[Any, Any]] = {}

    for fname, anno in annotations.items():
        if fname == '__pydantic_resolve_subset__':
            continue
        if fname in disallow:
            raise ValueError(f'additional field "{fname}" duplicates subset field')
        default = namespace.get(fname, ...)
        extras[fname] = (anno, default)

    return extras


def _normalize_unique_fields(fields: Any) -> List[str]:
    """Coerce incoming fields into a unique, ordered list of strings.

    Only accepts list or tuple. Other types raise TypeError. All elements must be strings.
    """
    if not isinstance(fields, (list, tuple)):
        raise TypeError('fields must be a list or tuple of field names')
    seq: List[Any] = list(fields)

    for f in seq:
        if not isinstance(f, str):
            raise TypeError('each field name must be a string')

    # Preserve order while removing duplicates
    return list(dict.fromkeys(seq))


def create_subset(parent: Type[BaseModel], fields: List[str], name: str = "SubsetModel") -> Type[BaseModel]:
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
    
    unique_fields = _normalize_unique_fields(fields)
    field_definitions = _extract_field_definitions_for_create_model(parent, unique_fields)
    validators = _get_parent_validators(parent, unique_fields)

    create_model_kwargs = {}
    config = _get_parent_config(parent)
    if config:
        create_model_kwargs['__config__'] = config
    
    subset_class = create_model(
        name,
        **field_definitions,
        **create_model_kwargs
    )

    _apply_validators(subset_class, validators)
    setattr(subset_class, const.ENSURE_SUBSET_REFERENCE, parent)
    return subset_class


class SubsetMeta(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        subset_info = namespace.get('__pydantic_resolve_subset__')
        if subset_info:
            parent_kls, picked_field = subset_info

            unique_fields = _normalize_unique_fields(picked_field)
            parent_fields = _extract_field_definitions_for_create_model(parent_kls, unique_fields)

            # Then extract extra fields defined in class body
            extra_fields = _extract_extra_fields_from_namespace(namespace, set(unique_fields))

            # Parent validators and config should still apply to subset fields
            create_model_kwargs: Dict[str, Any] = {}
            methods_to_attach: Dict[str, Any] = {}
            attributes_to_attach: Dict[str, Any] = {}

            validators = _get_parent_validators(parent_kls, unique_fields)
            config = _get_parent_config(parent_kls)
            if config:
                create_model_kwargs['__config__'] = config

            # Use the caller's module for better reprs and pickling
            create_model_kwargs['__module__'] = namespace.get('__module__', __name__)

            for nk, nv in namespace.items():
                if nk.startswith('__pydantic_resolve') and nk != '__pydantic_resolve_subset__':
                    attributes_to_attach[nk] = nv
                    continue

                if callable(nv) and (nk.startswith(const.RESOLVE_PREFIX) or nk.startswith(const.POST_PREFIX)):
                    methods_to_attach[nk] = nv


            # Merge field definitions: keep subset order first, then extras
            field_definitions: Dict[str, Tuple[Any, Any]] = {}
            field_definitions.update(parent_fields)
            field_definitions.update(extra_fields)

            print(create_model_kwargs)
            subset_class = create_model(
                name,
                **field_definitions,
                **create_model_kwargs
            )

            _apply_validators(subset_class, validators)

            for method_name, method in methods_to_attach.items():
                setattr(subset_class, method_name, method)
            for attr_name, attr_value in attributes_to_attach.items():
                setattr(subset_class, attr_name, attr_value)
            setattr(subset_class, const.ENSURE_SUBSET_REFERENCE, parent_kls)

            return subset_class
            
        # Allow defining the base marker class without warning, bypass
        if name == 'DefineSubset' and not bases:
            return super().__new__(cls, name, bases, namespace, **kwargs)

        raise ValueError(f'Class {name} must define __pydantic_resolve_subset__ to use SubsetMeta')

class DefineSubset(metaclass=SubsetMeta):
    pass
