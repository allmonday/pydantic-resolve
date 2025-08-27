# Add support for Union

current this case will raise exception becuase A, B inside C is not walked during analysis

which means they are not stored at metadata.

and then during resolving it will attempt to read A and B from metadata then exceptions are raised.

this feature aims to fix this bug.

```python
class A(BaseModel):
    id: int
    name: str

class B(BaseModel):
    id: int
    age: int

class C(BaseModel):
    items: List[Union[A, B]] = []
    def resolve(self):
        return [A(id=1, name='n'), B(id=1, age=21)]
```

for Union[A, B] pydantic-resolve will dive into A, B and store them in metadata.

## plan

- add `get_core_types` in types.py, will replace `shelling_type`
- check the code using `shelling_type` and their deps
  - class_utils.py
    - get_pydantic_fields: change the return type from type -> tuple of type
    - get_dataclass_fields
    - update_forward_refs
      - update_pydantic_forward_refs
      - update_dataclass_forward_refs
  - analysis.py
    - scan_and_store_metadata
      - \_get_all_fields_and_object_fields
    - object_field_pairs from \_get_all_fields_and_object_fields
      - \_get_request_type_for_loader: calculate receiver types for dataloader

## details

```python
def get_pydantic_fields(kls) -> Tuple[str, List[Type[BaseModel]]]:
    items = class_util.get_pydantic_field_items(kls)

    for name, v in items:
        t = get_type(v)

        shelled_types = get_core_types(t)
        expected_types = [t for t in shelled_types if is_acceptable_kls(t)]
        if expected_types:
            yield (name, expected_types)  # type_ is the most inner type
```

object_fields and object_field_pairs will be affected

```python
all_fields, object_fields, object_field_pairs = _get_all_fields_and_object_fields(kls)
```

object_fields:

```python

object_fields_without_resolver = [a[0] for a in object_fields if a[0] not in fields_with_resolver]

info: KlsMetaType = {
    'resolve': resolve_fields,
    'resolve_params': resolve_params,
    'post': post_fields,
    'post_params': post_params,
    'post_default_handler_params': post_default_handler_params,
    'raw_object_fields': object_fields_without_resolver,  # <----- here
    'object_fields': [],
    'expose_dict': expose_dict,
    'collect_dict': collect_dict,
    'kls': kls,
    'has_context': has_context,
    'should_traverse': False
}

for field, shelled_type in (obj for obj in object_fields if obj[0] in object_fields_without_resolver):
    walker(shelled_type, ancestors + [(field, kls_name)])
```
