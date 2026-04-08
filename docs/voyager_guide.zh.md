# Voyager 可视化指南

[English](./voyager_guide.md)

## fastapi-voyager 是什么

[fastapi-voyager](https://github.com/allmonday/fastapi-voyager) 是一个 FastAPI 应用的交互式可视化工具。它将你的 API 端点、Pydantic schema 和实体关系渲染为可导航的依赖图——让理解依赖、发现问题变得更直观，同时也可以作为活的文档使用。

与 pydantic-resolve 的 ER Diagram 配合使用时，fastapi-voyager 还能展示实体级别的关系图，清晰呈现你的领域模型。

## 安装

```bash
pip install fastapi-voyager
# 或
uv add fastapi-voyager
```

## 基本设置

将 Voyager 页面挂载到 FastAPI 应用中：

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager

app = FastAPI()

app.mount('/voyager', create_voyager(app))
```

在浏览器中打开 `/voyager`，即可看到所有端点及其依赖关系的交互式图谱。

## 展示 ER 图

当你已经用 pydantic-resolve 定义了 `ErDiagram` 时，将它传给 `create_voyager` 可以在 API 结构旁边可视化实体关系：

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager
from pydantic_resolve import ErDiagram, Entity, Relationship

diagram = ErDiagram(
    entities=[
        Entity(
            kls=SprintEntity,
            relationships=[
                Relationship(fk='id', target=list[TaskEntity], name='tasks', loader=task_loader),
            ],
        ),
        Entity(
            kls=TaskEntity,
            relationships=[
                Relationship(fk='owner_id', target=UserEntity, name='owner', loader=user_loader),
            ],
        ),
    ],
)

app = FastAPI()
app.mount('/voyager', create_voyager(app, er_diagram=diagram))
```

这会生成一个组合视图，你既能看到 API 端点层，也能看到底层的实体关系。

## 配置选项

`create_voyager` 接受以下可选参数：

| 参数 | 类型 | 描述 |
|------|------|------|
| `app` | `FastAPI` | FastAPI 应用实例 |
| `er_diagram` | `ErDiagram \| None` | pydantic-resolve ER Diagram，用于实体可视化 |
| `module_color` | `dict` | 模块路径与高亮颜色的映射（如 `{'src.services': 'tomato'}`） |
| `module_prefix` | `str \| None` | 只显示该模块前缀下的路由 |
| `swagger_url` | `str \| None` | Swagger 文档链接（如 `"/docs"`） |
| `initial_page_policy` | `str` | 首次显示哪个页面：`'first'` 或 `'all'` |
| `online_repo_url` | `str \| None` | 仓库源码链接的基础 URL |
| `enable_pydantic_resolve_meta` | `bool` | 显示 pydantic-resolve 元数据（resolve/post 标注） |

完整示例：

```python
app.mount(
    '/voyager',
    create_voyager(
        app,
        module_color={'src.services': 'tomato'},
        module_prefix='src.services',
        swagger_url="/docs",
        initial_page_policy='first',
        online_repo_url='https://github.com/example/my-project/blob/main',
        enable_pydantic_resolve_meta=True,
    ),
)
```

## 交互功能

### 高亮依赖

点击任意节点，高亮其上游和下游依赖。可以快速看到一个端点使用了哪些模型，或某个模型被哪些端点依赖。

### 查看源码

双击节点或路由可查看其源码。如果配置了 `online_repo_url`，还可以直接在 VS Code 中打开文件。

### 快速搜索

按名称搜索 schema 并展示其上下游关系。Shift+点击某个节点可立即搜索它。

### pydantic-resolve 元信息

当 `enable_pydantic_resolve_meta=True` 时，切换 "pydantic resolve meta" 视图可以看到每个 schema 上的 `resolve_*` 和 `post_*` 标注——方便一目了然地理解数据组装逻辑。

## 命令行使用

fastapi-voyager 还提供了 CLI 工具，无需启动服务器即可生成可视化：

```bash
# 在浏览器中打开
voyager -m path.to.your.app.module --server

# 自定义端口
voyager -m path.to.your.app.module --server --port=8002

# 生成 .dot 文件
voyager -m path.to.your.app.module

# 按 schema 名称过滤
voyager -m path.to.your.app.module --schema Task

# 显示所有字段
voyager -m path.to.your.app.module --show_fields all

# 自定义模块颜色
voyager -m path.to.your.app.module --module_color=tests.demo:red --module_color=tests.service:tomato

# 输出到文件
voyager -m path.to.your.app.module -o my_visualization.dot

# 选择特定的 FastAPI 应用（用于挂载的子应用场景）
voyager -m path.to.your.app.module --server --app api
```

## 在线演示

- [Voyager 演示](https://www.fastapi-voyager.top/voyager/) — 交互式 Voyager 可视化
- [GraphQL 演示](https://www.fastapi-voyager.top/graphql) — 由 pydantic-resolve 驱动的 GraphQL 端点
