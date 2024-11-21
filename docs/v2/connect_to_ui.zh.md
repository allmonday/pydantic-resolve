# 连接到 UI

pydantic 本身可以生成支持 OpenAPI 规范的 json schema。 这意味着它能够跨语言传递类型和方法等信息。

如果使用 FastAPI， 可以参考文档 [link](https://fastapi.tiangolo.com/advanced/generate-clients/?h=openapi.json#preprocess-the-openapi-specification-for-the-client-generator) 直接生成 typescript 的前端 sdk

这使得后端的改动可以直接传递到前端。

简单样例可以参考 repo： [pydantic-resolve-demo](https://github.com/allmonday/pydantic-resolve-demo)

借助 OpenAPI 和 sdk 生成， 前后端对接的成本直接锐减。

当后端数据结构发生变化之后， 前端同步之后也能第一时间借助 TypeScript 感知到变更。
