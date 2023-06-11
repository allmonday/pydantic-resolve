# Changelog

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
