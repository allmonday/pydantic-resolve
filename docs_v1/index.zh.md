# Install

Pydantic-resolve 是对 pydantic 的一个轻量级封装, 它可以为你构建复杂的视图数据提供便利

你只需简单地定义好pydantic schema (models), 然后让对应的resolve/ post 方法来处理剩下的事情

Pydantic (和fastapi 一起) 对 OpenAPI 的支持非常棒, 结合 [openapi-ts](https://github.com/hey-api/openapi-ts) 之后可以在前端快速生成 client 文件


如果使用的是 pydantic v1

```shell
pip install pydantic-resolve
```

如果使用的是 pydantic v2

```shell
pip install pydantic2-resolve
```

它们的API是相同的
