# Changelog

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
