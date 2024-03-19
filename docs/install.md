# Install

Pydantic-resolve is a light-weight wrapper library for pydantic, it can help you build complicated view data easily.

You only need to define your pydantic schemas/models and let resolvers/posts handle the rest.

Pydantic ifself plays pretty well with OpenAPI and can seamlessly integrated with frontend with [openapi-typescript-codegen](https://github.com/ferdikoomen/openapi-typescript-codegen), so that with pydantic-resolve you'll be able to construct accurate view data and transfer it to frontend.


if you are using pydantic v1:

```shell
pip install pydantic-resolve
```

if you are using pydantic v2:

```shell
pip install pydantic2-resolve
```


They share a same set of APIs