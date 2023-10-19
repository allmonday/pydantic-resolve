# Changelog

## v.1.7.1 (2023.10.19)

- fix raising error when `__pydantic_resolve_exposed__` field value is None

```python
class Bar(BaseModel):
    __pydantic_resolve_expose__ = {'num': 'bar_num'}  # expose {'bar_num': val }

    num: Optional[int]  # may be None
```

## v.1.7.0 (2023.9.2)

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

## v.1.6.5 (2023.8.12)

- `post_field` method and `post_default_handler` now can read context (setting in Resolver)

## v.1.6.4 (2023.8.7)

- some inside refactor

## v1.6.3 (2023.7.20)

- fix dataclass exception under lazy annotation. refer to `tests/resolver/test_28_parse_to_obj_for_dataclass_with_annotation.py`
- provide extra tip on auto map fails.

> recursion dataclass type is still not supported, refer to `test/resolver/test_26_tree.py`, L81

## v1.6.2 (2023.7.12)

- fix `output` minor bug

## v1.6.1 (2023.7.11)

- fix `output` decorator, it will modify schema_json's `required` field and fill all fields

## v1.6.0 (2023.7.11)

- add `Resolver.context` param
- remove `core.resolve`
- change `post_method`, return value will be assined to target field.
- add `output` decorator
- add `post_default_handler` for spacial use.

## v1.5.2 (2023.7.10)

- fix pydantic annotation related minor issue

## v1.5.1 (2023.7.9)

- fix the order of auto map, which will break the resolve chain

## v1.5.0 (2023.7.9) [has bug, do not use]

- new feature. the return value from resolve_method will be automatically converted to the type of target field, which means mapper with params of type is not required any more.
- if you `fromt __future__ import annotations` at top, make sure you define schemas in global scopes.

```python
    class Book(BaseModel):
        name: str

    async def batch_load_fn(keys):
        print('oader')
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

## v1.4.1 (2023.7.6)

- minor optimization, iteration of object attributes.

## v1.4.0 (2023.7.6)

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

## v1.3.2 (2023.7.4)

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

## v1.3.1 (2023.7.3)

- support `auto-mapping` from pydantic to pydantic and fix some testcases.

more detail: `tests/resolver/test_16_mapper.py`

- test_mapper_6
- test_mapper_7

## v1.3.0 (2023.6.27)

- add `Resolver.loader_instances` param, user can create loader before Resolver and this loader will be used inside. for example: you can prime value and to avoid extra query.

```python
loader = FriendLoader()
loader.prime('tangkikodo', ['tom', 'jerry'])
loader.prime('john', ['mike', 'wallace'])
result = await Resolver(loader_instances={FriendLoader: loader}).resolve(root)
# batch_load_fn will not run.
```

more detail: `tests/resolver/test_20_loader_instance.py`

## v1.2.2 (2023.6.21)

- minor adjustment, `build_list` and `build_object` will return iterator instead of list.

## v1.2.1 (2023.6.19)

- fix, modify `post_fieldname` execution position, reduce the duplication.

## v1.2.0 (2023.6.18)

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

## v1.1.1 (2023.6.17)

- extend @mapper decorator with target class option, this will call auto_mapping function inside.

```python
comments: List[CommentSchema]  = []
@mapper(CommentSchema)
def resolve_comments(self, loader=LoaderDepend(CommentLoader)):
    return loader.load(self.id)
```

## v1.1.0 (2023.6.16)

- add @mapper decorator, to enable custom data transform

```python
comments: List[CommentSchema]  = []
@mapper(lambda items: [CommentSchema.from_orm(item) for item in items])
def resolve_comments(self, loader=LoaderDepend(CommentLoader)):
    return loader.load(self.id)
```

## v1.0.0 (2023.6.11)

- support `batch_load_fn` as params for `LoaderDepend`
- add test `tests/resolver/test_15_support_batch_load_fn.py`
- `build_object`, `build_list` can be imported from `pydantic_resolve`

## v0.5.1 (2023.6.11)

- add helper utils for Dataloader.batch_load_fn `built_list` and `build_object`, see `examples/fastapi_demo/loader.py`
- FIX: fix potential error caused by same loader name from different module. see `tests/resolver/test_14_check_loader_name.py`

## v0.5.0 (2023.6.1)

- `Resolver.ensure_type`: True will ensure `resolve_*` methods have return annotation.
- add FastAPI integrated example `examples/fastapi_demo`

## v0.4.0 (2023.4.6)

- add new install option `pip install "pydantic-resolve[dataloader]" to include `aiodataloader` by default
- add new `doc/loader-cn.md`, `doc/loader-en.md` to explain the convinence of using `LoaderDepen`
- add new params in Resolver: `loader_filters` to support global filter setting for inside loaders.
- add `examples/6_sqlalchemy_loaderdepend_global_filter.md` for global filter

## v0.3.2 (2023.4.5)

- refact tests, group by `core` and `resolver`
- replace `unittest` with `pytest.mark.asyncio`
- little `readme.md` change, new top sample code

## v0.3.1 (2023.4.3)

- change code examples in readme.md
- add unittest for pydantic validationError
- code refactor (rename)

## v0.3.0

- add `DataloaderDependCantBeResolved`, it will raise if use `resolve` to handle schema with `Dataloader`
- add `chinese.md` and `english.md` in `doc` folder
