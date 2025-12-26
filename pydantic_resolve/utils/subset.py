from typing import Type, Dict, Any, List, Tuple, Set
from pydantic import BaseModel, create_model, model_validator
import copy
import pydantic_resolve.constant as const
from pydantic_resolve.utils.expose import ExposeAs
from pydantic_resolve.utils.collector import SendTo


class SubsetConfig(BaseModel): 
    kls: Type[BaseModel]  # parent class

    # fields and omit_fields are exclusive
    fields: List[str] | None = None
    omit_fields: List[str] | None = None

    # set Field(exclude=True) for these fields
    excluded_fields: List[str] | None = None

    expose_as: List[Tuple[str, str]] | None = None
    send_to: List[Tuple[str, Tuple[str, ...] | str]] | None = None

    @model_validator(mode='after')
    def validate_fields(self):
        if self.fields is not None and self.omit_fields is not None:
            raise ValueError("fields and omit_fields are exclusive")
        
        if self.fields is None and self.omit_fields is None:
            raise ValueError("fields or omit_fields must be provided")
        return self


def _extract_field_infos(kls: Type[BaseModel], field_names: List[str]) -> Dict[str, Any]:
    field_definitions = {}
    
    for field_name in field_names:
        field = kls.model_fields.get(field_name)
        if not field:
            raise AttributeError(f'field "{field_name}" not existed in {kls.__name__}')
        
        field_definitions[field_name] = (field.annotation, field)
    
    return field_definitions


def _get_kls_config(kls: Type[BaseModel]) -> Any:
    return getattr(kls, 'model_config', None)


def _get_kls_validators(kls: Type[BaseModel], field_names: List[str]) -> Dict[str, Any]:

    validators = {}
    decorators = getattr(kls, '__pydantic_decorators__', None)

    if decorators and hasattr(decorators, 'field_validators'):
        for validator_name, decorator_info in decorators.field_validators.items():
            # example: @field_validator('email', 'name') -> decorator_info.info.fields = ['email', 'name']
            if any(field in field_names for field in decorator_info.info.fields):
                validators[validator_name] = getattr(kls, validator_name)
    
    return validators


def _apply_validators(model_class: Type[BaseModel], validators: Dict[str, Any]) -> None:
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


class SubsetMeta(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        # subset_info is expected to be a tuple of (parent_class, list_of_field_names) or SubsetConfig
        subset_info = namespace.get(const.ENSURE_SUBSET_DEFINITION) or namespace.get(const.ENSURE_SUBSET_DEFINITION_SHORT)
            
        # Allow defining the base marker class without warning, bypass
        if name == 'DefineSubset' and not bases:
            return super().__new__(cls, name, bases, namespace, **kwargs)

        if not subset_info:
            raise ValueError(f'Class {name} must define {const.ENSURE_SUBSET_DEFINITION} to use SubsetMeta')

        if isinstance(subset_info, SubsetConfig):
            parent_kls = subset_info.kls

            if subset_info.fields is not None:
                subset_fields = subset_info.fields
            else:
                all_fields = list(parent_kls.model_fields.keys())
                omit_set = set(subset_info.omit_fields)
                subset_fields = [f for f in all_fields if f not in omit_set]
        else:
            parent_kls, subset_fields = subset_info

        _validate_subset_fields(subset_fields)
        field_infos = _extract_field_infos(parent_kls, subset_fields)

        if isinstance(subset_info, SubsetConfig):
            if subset_info.excluded_fields:
                for field_name in subset_info.excluded_fields:
                    if field_name in field_infos:
                        annotation, field_info = field_infos[field_name]
                        new_field_info = copy.deepcopy(field_info)
                        new_field_info.exclude = True
                        field_infos[field_name] = (annotation, new_field_info)

            if subset_info.expose_as:
                for field_name, alias in subset_info.expose_as:
                    if field_name in field_infos:
                        annotation, field_info = field_infos[field_name]
                        new_field_info = copy.deepcopy(field_info)
                        new_field_info.metadata.append(ExposeAs(alias))
                        field_infos[field_name] = (annotation, new_field_info)
            
            if subset_info.send_to:
                for field_name, target in subset_info.send_to:
                    if field_name in field_infos:
                        annotation, field_info = field_infos[field_name]
                        new_field_info = copy.deepcopy(field_info)
                        new_field_info.metadata.append(SendTo(target))
                        field_infos[field_name] = (annotation, new_field_info)

        # Then extract extra fields defined in class body
        extra_fields = _extract_extra_fields_from_namespace(namespace, set(subset_fields))

        # Parent validators and config should still apply to subset fields
        create_model_kwargs: Dict[str, Any] = {}
        attributes_to_attach: Dict[str, Any] = {}
        methods_to_attach: Dict[str, Any] = {}

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


class DefineSubset(metaclass=SubsetMeta):
    pass
