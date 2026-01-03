# Changelog

## v2.4

### v2.4.3 (2026-1-3)

- fix:
    - fix dict_keys in generating openapi.json

### v2.4.2 (2026-1-3) - yanked
- fix:
    - model_config should convert all fields into required status (for serialization)
- enhancement:
    - friendly error message in er diagram module

### v2.4.1 (2025-12-26)

- feat:
    - SubsetConfig's fields now support "all" to select all fields


### v2.4.0 (2025-12-26)

```python
class NewSub(DefineSubset):
    __subset__ = SubsetConfig(
        kls=Parent,
        fields=['id', 'name', 'age'],
        exclude_fields=['name'],  # Field(exclude=True)
        expose_as=[('name', 'custom_name')],
        send_to=[
            ('age', 'age_collector'),
            ('age', ('a', 'b')) 
        ],
    )
```
        
- feat:
    - better subset configuration
- refactor:
    - move loader_manager into seperate module
- doc:
    - add more comments 

## v2.3

### v2.3.3

hotfix:

```shell
  File "/usr/local/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/usr/local/lib/python3.12/site-packages/starlette/routing.py", line 75, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 334, in app
    content = await serialize_response(
              ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 188, in serialize_response
    return field.serialize(
           ^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/_compat.py", line 152, in serialize
    return self._type_adapter.dump_python(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/pydantic/type_adapter.py", line 572, in dump_python
    return self.serializer.to_python(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: 'mappingproxy' object cannot be converted to 'PyDict'
```

### v2.3.2
- optimization:
    - provide proper type annotation for `base_entity` method
- refactor:
    - clean up unused files

### v2.3.1
- feat:
    - add `__subset__` short name for `__pydantic_resolve_subset__`

### v2.3.0

- feat: 
    - add `SendTo` and `ExposeAs` to simplify / replace `__pydantic_resolve_collect__` and `__pydantic_resolve_expose__`, read: test_52 and test_53 for more details
    - add `__relationships__` short name for `__pydantic_resolve_relationships__`
- fix: clean print

## v2.2

### v2.2.4 (2025.12.8)

fix: ignore inherited descendant in inline relationship definition

more details in test case: `tests/er_diagram/test_er_diagram_base.py`


### v2.2.3 (2025.12.7)

feat: for ininline relationships str are allowed to represent the class name

for example, use `target_kls='User'` if User is defined after current class

```python
class Biz(BaseModel, BaseEntity):
    __pydantic_resolve_relationships__ = [
        Relationship(field='user_id', target_kls='User', loader=UserLoader),
        Relationship(field='id', target_kls=list[Bar], field_none_default_factory=list, loader=BarLoader),
    ]
    id: Optional[int]
    name: str
    user_id: Optional[int]

class User(BaseModel):
    ...
```

Only use this in inline mode.

### v2.2.2 (2025.12.5)

feat: add origin_kls in LoadBy to avoid blurring during matching loader

### v2.2.1 (2025.12.5)

feat: add field_fn in er diagram, receive callable object to process key before loader.load

### v2.2.0 (2025.12.5)

feat: relationship can be defined inside class
```python
class Biz(BaseModel, BaseEntity):
    __pydantic_resolve_relationships__ = [
        Relationship(field='user_id', target_kls=User, loader=UserLoader),
        Relationship(field='id', target_kls=list[Bar], field_none_default_factory=list, loader=BarLoader),
    ]
    id: Optional[int]
    name: str
    user_id: Optional[int]

MyResolver = config_resolver('MyResolver', er_diagram=BaseEntity.get_diagram())
# or
# config_global_resolver(er_diagram=BaseEntity.get_diagram())
```

## v2.1

### v2.1.0 (2025.11.29)
- change: 
    - inside ErDiagram, `biz` of Relationship is moved into Link, and is not Opitonal anymore
- feature:
    - add MultipleRelationship for scenarios having mulitple links between entity and target_entity.

## v2.0

### v2.0.1 (2025.11.26)
- rename `ErConfig` to `Entity` (caution: will break current code)

### v2.0.0 (2025.11.26)
- release

### v2.0.0a5 (2025.11.25)
- feat:
    - support load_many in Relationship

### v2.0.0a4 (2025.11.23)
- refactor:
    - optimize ErPreGenerator

### v2.0.0a3 (2025.11.19)
- fix:
    - DefineSubset lost resolve/post methods and `__pydantic_resolve_xxx__` configs

### v2.0.0a2 (2025.11.17)
- fix:
    - raise ValueError if er_diagram are not provided when LoadBy are used in somewhere
    - relationship.loader is optional, but required if used in LoadBy 

### v2.0.0a1 (2025.11.16)
- features:
    - add `er_diagram` to define application level entity relationships.
    - add `config_resolver` and `config_global_resolver` to bind Resolver with er_diagram.
    - a new version of subset: `DefineSubset`.
- enhancements:
    - caching metadata generated during analysis process
- breaks:
    - remove support of pydantic v1 and dataclass
    - 3.10 now is the minimal requirement

## v1.13

### v1.13.5 (2025.10.23)

- add annotation param in Resolver to specify the root class when resolving list of Union types.
    - refer to `tests/common/test_annotation_param.py`
- support type alias: `type U = A | B` 

### v1.13.4 (2025.10.14)

- fix memory leak due inner function closure

### v1.13.3 (2025.10.13)

- fix memory leak due to haven't properly reset contextvars.ContextVar

### v1.13.2 (2025.9.4)

- minor: @ensure_subset(base_kls) will attach kls info into target class, prepare for dependency analysis in future

### v1.13.1 (2025.8.28)

- fix: add support for UnionType such as `A | B`
- update: upgrade python version to 3.10 in ci

### v1.13.0 (2025.8.27)

feature:

- add support for resolving Union[A, B]
  - **known issue**: for pydantic v1, use it in caution, union_smart not yet works with `parse_obj_as`, see `tests/pydantic_v1/resolver/test_43_union_bad.py`
  - it fully support pydantic v2
  - prefer to return pydantic/dataclass object instead of dict

## v1.12

### v1.12.5 (2025.7.24)

feature:

- add short name `Loader` for `LoaderDepend`
- set Loader return type as DataLoader

non-functional:

- add more tests
- rename internal variable names

### v1.12.4 (2025.7.12)

update python versions in pyproject.toml

### v1.12.3 (2025.6.29)

enhancement the support to dataclass

- update model_config decorator to also support dataclass.
- return annotation now supports `Union[T, None]` for `sys.version_info > (3.7)`
- ensure_subset support dataclass

### v1.12.2 (2025.6.20)

fix:

if DataLoader fields already has default value, Resolver.loader_params can skip them and will not raise `LoaderFieldNotProvidedError` any more.

```python
class LoaderA(DataLoader):
    power: int = 2
    async def batch_load_fn(self, keys: List[int]):
        return [ k** self.power for k in keys ]

class A(BaseModel):
    val: int

    a: int = 0
    def resolve_a(self, loader=LoaderDepend(LoaderA)):
        return loader.load(self.val)

@pytest.mark.asyncio
async def test_case():
    """
    default param allow not setting loader param in Resolver
    """
    data = [A(val=n) for n in range(3)] # 0, 1, 2 => 0, 1, 4
    data = await Resolver().resolve(data)
    assert data[2].a == 4

@pytest.mark.asyncio
async def test_case_2():
    """
    default param can be overridden in Resolver
    """
    data = [A(val=n) for n in range(3)] # 0, 1, 2 => 0, 1, 4
    data = await Resolver(
        loader_params={
            LoaderA: {'power': 3}  # override default power
        }
    ).resolve(data)
    assert data[2].a == 8
```

### v1.12.1 (2025.6.1)

feature:

inside dataloader object, we can read the request return types / request fiels from `_query_meta` field.

```python
class SampleLoader(DataLoader):
    async def batch_load_fn(self, keys):
        print(self._query_meta['fields']) # => ['id', 'name']
        print(self._query_meta['request_types']) # => [ {'name': Student, 'fields': ['id', 'name'] } ]

        data = await query_students(self._query_meta['fields'], keys)
        # select id, name from xxxxx

        return build_list(data, keys, lambda d: d.id)

class Student(BaseModel):
    id: int
    name: str

class ClassRoom(BaseModel):
    id: int
    name: str

    students: List[Student] = []
    def resolve_students(self, loader=LoaderDepend(SampleLoader)):
        return loader.load(self.id)
```

### v1.12.0 (2025.5.24)

optimization:

improve the algorithm of analysising object_fields, it helps skip nodes that don't need processing.
using a back populate approach, now it can handle loop scenaio.

refer:

- `tests/common/test_analysis_object_fields.py` 1,2,3,4

```
┌────────┐
│   Kls  │
└────────┘
    │       ┌─────────────────┐
    │       │ ┌──────────┐    │
    │       ▼ ▼          │    │
    │     ┌─────┐        x(o) o
    ├─o───│ Tree│────────┘    │
    │     └─────┘─────────────┘
    │
    │
    │         ┌───────┐
    │         │       │
    │         ▼       x
    │     ┌──────┐    │
    ├─x───│ Tree2│ ───┘
    │     └──────┘
    │
    │         ┌─────────o─────────┐
    │         │                   │
    │         ▼                   │
    │     ┌───────┐           ┌───────┐
    ├──o──│ Tree31│─────x────►│Tree32 │
    │     └───────┘           └───────┘
    │
    │         ┌───────┐
    │         │       │
    │         ▼       o
    │     ┌──────┐    │
    └─x───│ Tree4│ ───┘
          └──────┘
```

## v1.11

### v1.11.10 (2025.5.12)

bug:

optimize the hit logic during analysising the class

fix a corner case of wrongly marking a class as 'no resolve'

### v1.11.9 (2025.5.7)

bug:

details in testcase: `test/common/test_long_distance_resolve.py`

before ver: 1.11.8
d, or e will be removed from the object_fields
it is due to the \_has_config function do not verify the len of
object_fields.

but in fact, if a kls is cached, it should not take party in judging
`should_treverse`, so from 1.11.9 it will return None

for self reference data structure, object fields will always be kept

details in test case `test/common/test_long_distance_resolve_recursive.py`

### v1.11.8 (2025.3.31)

bug:

- [pydantic v2] fix `adapter.validate_python` raise exception when parse from another pydantic object (which is not exactly the same with target class)

### v1.11.7 (2025.3.21)

feat:

- optimize the output of debug (profile)

### v1.11.6 (2025.3.19)

bug:

- fix debug generate multiple logging due to add handler multiple times in constructor.

### v1.11.5 (2025.3.19)

bug:

- post method should not further resolve the target, it will cause the lost of ancestor using with collector
- and this behavior also conflicts with the purpose of data adjustment and re-organization only

### v1.11.4 (2025.3.19)

feature:

- add debug field to display time consuming of each node.

### v1.11.3 (2024.12.12)

- if an object field and its descendants does not has pydantic-resolve related configs, it will be skipped during the traversal.

### v1.11.2 (2024.11.22)

- return value from post method will also be recursively traversed and resolved.
- add dataloader params in post method

### v1.11.1 (2024.11.21)

- refactor fold structure
- new documentation

### v1.11.0 (2024.10.24)

- support pydantic v2 (archive lib pydantic2-resolve)
- remove hidden_fields in model_config

## v1.10

### v1.10.8 (2024.8.27)

- collector suppor tuple for value

```python
class Item(BaseModel):
    __pydantic_resolve_collect__ = {('field_a', 'field_b'): ('collector_a', 'collector_b')}
```

this means `(Item.field_a, Item.field_b)` will be sent to both collector_a and collector_b

### v1.10.7 (2024.8.16)

- collector support tuple

```python
class Item(BaseModel):
    __pydantic_resolve_collect__ = {('field_a', 'field_b'): 'collector_name'}
```

### v1.10.6 (2024.8.12)

- collector now can collect from multiple sources

### v1.10.5 (2024.5.20)

- post method can be async function

### v1.10.4 (2024.4.11)

- new feature: reading parent node in resolve, post and post_default_handler

### v1.10.3 (2024.4.8)

- bugfix, handle TypeError from issubclass, https://github.com/allmonday/pydantic2-resolve/issues/7

### v1.10.2 (2024.3.21)

- internal optimization:
  - no more inspect.signature in runtime

### v1.10.1 (2024.3.17)

- fix collect intermediate level error
- internal refactor
  - better metadata lookup

### ~~v1.10.0 (2024.3.16)~~

- add new feature: `collector`
- internal refactor
  - optimize scan process.
  - prepare for debug feature.
  - create dataloader instance before resolving

## v1.9

### v1.9.3 (2024.03.12)

- rename loader_filter -> loader_params
- rename global_loader_filter -> global_loader_param

using old params will have warning messages.

### v1.9.2 (2024.02.03)

- bugfix for model_config
  - setting `__exclude_fields__` should not put in schema_extra.

### v1.9.1 (2024.02.02)

- add new decorator `model_config`:
  - control hidden fields (for schema() and dict())
  - built-in required in schema

### v1.9.0 (2024.01.22)

- add `global_loader_filter` for convinence. (thanks Dambre)

## v1.8

### v1.8.2 (2023.12.20)

- fix corner case of empty list input. `tests/core/test_input.py`

### v1.8.1 (2023.12.16)

- fix scan exceptions caused from pydantic `.type_` value of `List[Optional[T]]`

### v1.8.0 (2023.12.15)

- internal refactor: performance improvement
- remove Resolver.annotation_class, it will be processed automatically
- new helper function `copy_dataloader_kls` to generate a copy of DataLoader
- `pydantic_resolve.utils` provide several internal `generate_loader` functions.

## v1.7

### v1.7.2 (2023.11.16)

- fix overwriting BaseModel.Config.schema_extra in `@input`

### v1.7.1 (2023.10.19)

- fix raising error when `__pydantic_resolve_exposed__` field value is None

```python
class Bar(BaseModel):
    __pydantic_resolve_expose__ = {'num': 'bar_num'}  # expose {'bar_num': val }

    num: Optional[int]  # may be None
```

### v1.7.0 (2023.9.2)

- add a port in ancestor class to expose value of specific field to its descendants.
- resolve_field and post_field of descendant class can read those from `ancestor_context`
- DO NOT EXPOSE resolver_fields (eg Bar.kars, Kar.desc), it is empty by default.

```python
class Kar(BaseModel):
    name: str

    desc: str = ''
    def resolve_desc(self, ancestor_context):
        return f"{self.name} - {ancestor_context['bar_num']}"  # read ancestor value from 'ancestor_context'


class Bar(BaseModel):
    __pydantic_resolve_expose__ = {'num': 'bar_num'}  # expose {'bar_num': val }

    num: int

    kars: List[Kar] = []
    def resolve_kars(self):
        return [{'name': n} for n in ['a', 'b', 'c']]


class Foo(BaseModel):
    nums:List[int]
    bars: List[Bar] = []

    def resolve_bars(self):
        return [{'num': n} for n in self.nums]

```

## v1.6

### v1.6.5 (2023.8.12)

- `post_field` method and `post_default_handler` now can read context (setting in Resolver)

### v1.6.4 (2023.8.7)

- some inside refactor

### v1.6.3 (2023.7.20)

- fix dataclass exception under lazy annotation. refer to `tests/resolver/test_28_parse_to_obj_for_dataclass_with_annotation.py`
- provide extra tip on auto map fails.

> recursion dataclass type is still not supported, refer to `test/resolver/test_26_tree.py`, L81

### v1.6.2 (2023.7.12)

- fix `output` minor bug

### v1.6.1 (2023.7.11)

- fix `output` decorator, it will modify schema_json's `required` field and fill all fields

### v1.6.0 (2023.7.11)

- add `Resolver.context` param
- remove `core.resolve`
- change `post_method`, return value will be assined to target field.
- add `output` decorator
- add `post_default_handler` for spacial use.

## v1.5

### v1.5.2 (2023.7.10)

- fix pydantic annotation related minor issue

### v1.5.1 (2023.7.9)

- fix the order of auto map, which will break the resolve chain

### ~~v1.5.0 (2023.7.9)~~

- new feature. the return value from resolve_method will be automatically converted to the type of target field, which means mapper with params of type is not required any more.
- if you `fromt __future__ import annotations` at top, make sure you define schemas in global scopes.

```python
    class Book(BaseModel):
        name: str

    async def batch_load_fn(keys):
        books = [[bb for bb in BOOKS.get(k, [])] for k in keys]
        return books

    class Student(BaseModel):
        id: int
        name: str

        books: List[Book] = []
        def resolve_books(self, loader=LoaderDepend(batch_load_fn)):
            return loader.load(self.id)  # auto convert dict into Book type

    class ClassRoom(BaseModel):
        students: List[Student]


    students = [Student(id=1, name="jack"), Student(id=2, name="mike"), Student(id=3, name="wiki")]
    classroom = ClassRoom(students=students)
    classroom = await Resolver().resolve(classroom)
    assert isinstance(classroom.students[0].books[0], Book)
```

- recommend: using `mapper` with lambda only

## v1.4

### v1.4.1 (2023.7.6)

- minor optimization, iteration of object attributes.

### v1.4.0 (2023.7.6)

- support resolve through objects which intermediate items has not `resolve_` methods.

more detail: `tests/resolver/test_21_not_stop_by_idle_level.py`

```python
class C(BaseModel):
    name: str = ''

class B(BaseModel):
    name: str
    c: Optional[C] = None
    async def resolve_c(self) -> Optional[C]:
        await asyncio.sleep(1)
        return C(name='hello world')

class A(BaseModel):
    b: B

class Z(BaseModel):
    a: A
    resolve_age: int

@pytest.mark.asyncio
async def test_resolve_object():
    s = Z(a=A(b=B(name="kikodo")), resolve_age=21)  # resolve starts from B

    result = await Resolver().resolve(s)
```

## v1.3

### v1.3.2 (2023.7.4)

- add subset check decorator `ensure_subset`.

```python
    class Base(BaseModel):
        a: str
        b: int

    @util.ensure_subset(Base)
    class ChildA(BaseModel):
        a: str

    @util.ensure_subset(Base)
    class ChildB(BaseModel):
        a: str
        c: int = 0
        def resolve_c(self):
            return 21

    @util.ensure_subset(Base)
    class ChildB(BaseModel):
        a: int  # raise attribute error
```

### v1.3.1 (2023.7.3)

- support `auto-mapping` from pydantic to pydantic and fix some testcases.

more detail: `tests/resolver/test_16_mapper.py`

- test_mapper_6
- test_mapper_7

### v1.3.0 (2023.6.27)

- add `Resolver.loader_instances` param, user can create loader before Resolver and this loader will be used inside. for example: you can prime value and to avoid extra query.

```python
loader = FriendLoader()
loader.prime('tangkikodo', ['tom', 'jerry'])
loader.prime('john', ['mike', 'wallace'])
result = await Resolver(loader_instances={FriendLoader: loader}).resolve(root)
# batch_load_fn will not run.
```

more detail: `tests/resolver/test_20_loader_instance.py`

## v1.2

### v1.2.2 (2023.6.21)

- minor adjustment, `build_list` and `build_object` will return iterator instead of list.

### v1.2.1 (2023.6.19)

- fix, modify `post_fieldname` execution position, reduce the duplication.

### v1.2.0 (2023.6.18)

- add `post_fieldname` method, it will be called after the object is fully resolve as a hook, developer can run some aggregation computation. `tests/resolver/test_18_post_methods.py`

```python
class Friend(BaseModel):
    name: str

    cash: Optional[Cash] = None
    @mapper(Cash)  # auto mapping
    def resolve_cash(self, contact_loader=LoaderDepend(cash_batch_load_fn)):
        return contact_loader.load(self.name)

    has_cash: bool = False
    def post_has_cash(self):    # <----------------------
        self.has_cash = self.cash is not None

class User(BaseModel):
    name: str
    age: int

    friends: List[Friend] = []
    @mapper(lambda names: [Friend(name=name) for name in names])
    def resolve_friends(self, friend_loader=LoaderDepend(friends_batch_load_fn)):
        return friend_loader.load(self.name)

    has_cash: bool = False
    def post_has_cash(self):    # <----------------------
        self.has_cash = any([f.has_cash for f in self.friends])
```

## v1.1

### v1.1.1 (2023.6.17)

- extend @mapper decorator with target class option, this will call auto_mapping function inside.

```python
comments: List[CommentSchema]  = []
@mapper(CommentSchema)
def resolve_comments(self, loader=LoaderDepend(CommentLoader)):
    return loader.load(self.id)
```

### v1.1.0 (2023.6.16)

- add @mapper decorator, to enable custom data transform

```python
comments: List[CommentSchema]  = []
@mapper(lambda items: [CommentSchema.from_orm(item) for item in items])
def resolve_comments(self, loader=LoaderDepend(CommentLoader)):
    return loader.load(self.id)
```

## v1.0

### v1.0.0 (2023.6.11)

- support `batch_load_fn` as params for `LoaderDepend`
- add test `tests/resolver/test_15_support_batch_load_fn.py`
- `build_object`, `build_list` can be imported from `pydantic_resolve`

## v0.5

### v0.5.1 (2023.6.11)

- add helper utils for Dataloader.batch_load_fn `built_list` and `build_object`, see `examples/fastapi_demo/loader.py`
- FIX: fix potential error caused by same loader name from different module. see `tests/resolver/test_14_check_loader_name.py`

### v0.5.0 (2023.6.1)

- `Resolver.ensure_type`: True will ensure `resolve_*` methods have return annotation.
- add FastAPI integrated example `examples/fastapi_demo`

## v0.4

### v0.4.0 (2023.4.6)

- add new install option `pip install "pydantic-resolve[dataloader]" to include `aiodataloader` by default
- add new `doc/loader-cn.md`, `doc/loader-en.md` to explain the convinence of using `LoaderDepen`
- add new params in Resolver: `loader_filters` to support global filter setting for inside loaders.
- add `examples/6_sqlalchemy_loaderdepend_global_filter.md` for global filter

## v0.3

### v0.3.2 (2023.4.5)

- refact tests, group by `core` and `resolver`
- replace `unittest` with `pytest.mark.asyncio`
- little `readme.md` change, new top sample code

### v0.3.1 (2023.4.3)

- change code examples in readme.md
- add unittest for pydantic validationError
- code refactor (rename)

### v0.3.0

- add `DataloaderDependCantBeResolved`, it will raise if use `resolve` to handle schema with `Dataloader`
- add `chinese.md` and `english.md` in `doc` folder
