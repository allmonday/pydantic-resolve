from typing import Type, Dict, Any, List, Tuple, Optional, Union
from pydantic import BaseModel, create_model
from pydantic_resolve.compat import PYDANTIC_V2

if PYDANTIC_V2:
    from pydantic import Field
else:
    from pydantic import Field


def _extract_field_definitions_for_create_model_v1(parent: Type[BaseModel], field_names: List[str]) -> Dict[str, Tuple]:
    """Extract field definitions in format suitable for create_model (Pydantic v1)."""
    field_definitions = {}
    
    for fname in field_names:
        fld = parent.__fields__.get(fname)  # In v1 this is a ModelField object
        if not fld:
            raise AttributeError(f'field "{fname}" not existed in {parent.__name__}')
        
        # In v1, access field type via outer_type_ attribute
        field_type = fld.outer_type_  # type: ignore
        
        if fld.required:  # type: ignore
            field_definitions[fname] = (field_type, ...)
        else:
            # For non-required fields, use default
            field_definitions[fname] = (field_type, fld.default)  # type: ignore
    
    return field_definitions


def _extract_field_definitions_for_create_model_v2(parent: Type[BaseModel], field_names: List[str]) -> Dict[str, Tuple]:
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


_extract_field_definitions_for_create_model = _extract_field_definitions_for_create_model_v2 if PYDANTIC_V2 else _extract_field_definitions_for_create_model_v1


def _get_parent_config_v1(parent: Type[BaseModel]) -> Any:
    """Get parent's configuration (Pydantic v1)."""
    return getattr(parent, 'Config', None)


def _get_parent_config_v2(parent: Type[BaseModel]) -> Any:
    """Get parent's configuration (Pydantic v2)."""
    return getattr(parent, 'model_config', None)


_get_parent_config = _get_parent_config_v2 if PYDANTIC_V2 else _get_parent_config_v1


def _get_parent_validators_v1(parent: Type[BaseModel], field_names: List[str]) -> Dict[str, Any]:
    """Get parent's validators relevant to the subset fields (Pydantic v1)."""
    validators = {}
    
    # In v1, check for @validator decorated methods
    for attr_name, value in parent.__dict__.items():
        if callable(value) and attr_name.startswith('validate_'):
            # Check if this validator is for one of our fields
            field_name = attr_name.replace('validate_', '')
            if field_name in field_names:
                validators[attr_name] = value
    
    return validators


def _get_parent_validators_v2(parent: Type[BaseModel], field_names: List[str]) -> Dict[str, Any]:
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


_get_parent_validators = _get_parent_validators_v2 if PYDANTIC_V2 else _get_parent_validators_v1


def _apply_validators_v1(model_class: Type[BaseModel], validators: Dict[str, Any], create_model_kwargs: Dict[str, Any]) -> None:
    """Apply validators to Pydantic v1 model through create_model."""
    if validators:
        create_model_kwargs['__validators__'] = validators


def _apply_validators_v2(model_class: Type[BaseModel], validators: Dict[str, Any], create_model_kwargs: Dict[str, Any]) -> None:
    """Apply validators to Pydantic v2 model after creation."""
    # In v2, validators are handled differently and need to be copied manually
    # This is a simplified approach - the proper way would be to use pydantic's internal mechanisms
    for name, validator in validators.items():
        setattr(model_class, name, validator)
    
    # Note: This approach has limitations - the validators might not be properly registered
    # with Pydantic's validation system. For full compatibility, we'd need to recreate
    # the __pydantic_decorators__ structure, which is complex.
    # For now, this is a basic implementation that copies the methods.


_apply_validators = _apply_validators_v2 if PYDANTIC_V2 else _apply_validators_v1


def _apply_config_v1(subset_class: Type[BaseModel], config: Any, create_model_kwargs: Dict[str, Any]) -> None:
    """Apply config to Pydantic v1 model through create_model."""
    if config:
        create_model_kwargs['__config__'] = config


def _apply_config_v2(subset_class: Type[BaseModel], config: Any, create_model_kwargs: Dict[str, Any]) -> None:
    """Apply config to Pydantic v2 model through create_model."""
    if config:
        create_model_kwargs['__config__'] = config


_apply_config = _apply_config_v2 if PYDANTIC_V2 else _apply_config_v1


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
    
    # Remove duplicates while preserving order
    unique_fields = list(dict.fromkeys(fields))
    
    # Extract field definitions for create_model
    field_definitions = _extract_field_definitions_for_create_model(parent, unique_fields)
    
    # Get parent configuration and validators
    config = _get_parent_config(parent)
    validators = _get_parent_validators(parent, unique_fields)
    
    # Prepare create_model arguments
    create_model_kwargs = {}
    
    # Apply config through create_model_kwargs for both versions
    _apply_config(None, config, create_model_kwargs)  # type: ignore
    
    # Apply validators through create_model_kwargs only for v1
    if not PYDANTIC_V2:
        _apply_validators(None, validators, create_model_kwargs)  # type: ignore
    
    # Use create_model to generate the subset class
    subset_class = create_model(
        name,
        **field_definitions,
        **create_model_kwargs
    )
    
    # For Pydantic v2, apply validators after model creation
    if PYDANTIC_V2:
        _apply_validators(subset_class, validators, {})
    
    return subset_class
    
    return subset_class


    