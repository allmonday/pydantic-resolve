# 为何从GraphQL 转到了 Pydantic-resolve

1. GraphQL的优势是方便构建嵌套结构，方便生成查询子集。非常适合构建灵活的public API.
2. 后端采用GraphQL的话，可以方便地组织嵌套地数据结构，还能暴露出一个灵活的查询接口。但是很多实际业务在前端做的其实是**照单全收**，并没有灵活选择的需要。更多地便利来自于嵌套结构。
3. 相较于通过`openapi.json`自动生成client让前后端无缝连接，GraphQL还需要client端维护查询语句，在前后端一体的架构中，这种做法属于重复劳动。
4. 对于内部使用的API，结合权限控制的需要，通过RestFUL定义一个个API 比全局一个Query，Mutation 控制起来更加清晰直接。

> 结论：GraphQL更适合 public API, 对**前后端作为一个整体**的项目，`RESTful` + `pydantic-resolve` 才是灵活提供数据结构的最佳方法。