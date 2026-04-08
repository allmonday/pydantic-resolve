# Voyager Visualization Guide

[中文版](./voyager_guide.zh.md)

## What Is fastapi-voyager

[fastapi-voyager](https://github.com/allmonday/fastapi-voyager) is an interactive visualization tool for FastAPI applications. It renders your API endpoints, Pydantic schemas, and entity relationships as a navigable graph — making it easier to understand dependencies, spot issues, and serve as living documentation.

When used together with pydantic-resolve's ER Diagram, fastapi-voyager can also display entity-level relationship diagrams, giving a clear view of your domain model.

## Installation

```bash
pip install fastapi-voyager
# or
uv add fastapi-voyager
```

## Basic Setup

Mount the Voyager page into your FastAPI application:

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager

app = FastAPI()

app.mount('/voyager', create_voyager(app))
```

Open `/voyager` in your browser to see the interactive graph of all your endpoints and their dependencies.

## Displaying ER Diagrams

When you have an `ErDiagram` defined with pydantic-resolve, pass it to `create_voyager` to visualize entity relationships alongside your API structure:

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager
from pydantic_resolve import ErDiagram, Entity, Relationship

diagram = ErDiagram(
    configs=[
        Entity(
            kls=SprintEntity,
            relationships=[
                Relationship(field='id', target_kls=list[TaskEntity], loader=task_loader),
            ],
        ),
        Entity(
            kls=TaskEntity,
            relationships=[
                Relationship(field='owner_id', target_kls=UserEntity, loader=user_loader),
            ],
        ),
    ],
)

app = FastAPI()
app.mount('/voyager', create_voyager(app, er_diagram=diagram))
```

This produces a combined view where you can see both the API endpoint layer and the underlying entity relationships.

## Configuration Options

`create_voyager` accepts several optional parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `app` | `FastAPI` | Your FastAPI application instance |
| `er_diagram` | `ErDiagram \| None` | pydantic-resolve ER Diagram for entity visualization |
| `module_color` | `dict` | Map module paths to highlight colors (e.g. `{'src.services': 'tomato'}`) |
| `module_prefix` | `str \| None` | Filter to only show routes under this module prefix |
| `swagger_url` | `str \| None` | Link to your Swagger docs (e.g. `"/docs"`) |
| `initial_page_policy` | `str` | Which page to show first: `'first'` or `'all'` |
| `online_repo_url` | `str \| None` | Base URL for linking nodes to source code in your repository |
| `enable_pydantic_resolve_meta` | `bool` | Show pydantic-resolve metadata (resolve/post annotations) |

Full example:

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

## Interactive Features

### Highlight Dependencies

Click any node to highlight its upstream and downstream dependencies. This lets you quickly see which models an endpoint uses, or which endpoints depend on a specific model.

### View Source Code

Double-click a node or route to view its source code. If `online_repo_url` is configured, it can also open the file directly in VS Code.

### Quick Search

Search schemas by name and display their upstream and downstream relationships. Shift+click on a node to search for it immediately.

### pydantic-resolve Meta

When `enable_pydantic_resolve_meta=True`, toggle the "pydantic resolve meta" view to see `resolve_*` and `post_*` annotations on each schema — useful for understanding the data assembly logic at a glance.

## Command Line Usage

fastapi-voyager also provides a CLI for generating visualizations without running a server:

```bash
# Open in browser
voyager -m path.to.your.app.module --server

# Custom port
voyager -m path.to.your.app.module --server --port=8002

# Generate .dot file
voyager -m path.to.your.app.module

# Filter by schema name
voyager -m path.to.your.app.module --schema Task

# Show all fields
voyager -m path.to.your.app.module --show_fields all

# Custom module colors
voyager -m path.to.your.app.module --module_color=tests.demo:red --module_color=tests.service:tomato

# Output to file
voyager -m path.to.your.app.module -o my_visualization.dot

# Select a specific FastAPI app (for mounted sub-applications)
voyager -m path.to.your.app.module --server --app api
```

## Live Demo

- [Online Demo](https://www.fastapi-voyager.top/voyager/) — Interactive Voyager visualization
- [GraphQL Demo](https://www.fastapi-voyager.top/graphql) — GraphQL endpoint powered by pydantic-resolve
