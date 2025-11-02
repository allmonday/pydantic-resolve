from typing import Type, Dict, Any, List, Tuple
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
    
    unique_fields = list(dict.fromkeys(fields))
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
    