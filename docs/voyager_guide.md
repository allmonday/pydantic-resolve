---
description: Generate an interactive ERD visualization for your FastAPI app with fastapi-voyager — see how endpoints and Pydantic schemas connect without reading source files. Mounts at a single URL, reads your ERD directly.
---

# Voyager Visualization

[中文版](./voyager_guide.zh.md)

This page solves one problem: your FastAPI app has dozens of endpoints and Pydantic schemas, and you need a visual map to understand how they connect — without reading source files one by one.

## Goal

You have this:

```python
app = FastAPI()

@app.get("/tasks", response_model=list[TaskView])
async def get_tasks(): ...

@app.get("/sprints/{sprint_id}", response_model=SprintView)
async def get_sprint(sprint_id: int): ...
```

You want this — an interactive graph where you can click any endpoint or schema and immediately see its dependencies:

```
┌─────────────┐     ┌──────────┐     ┌──────────┐
│ GET /tasks  │────▶│ TaskView │────▶│ UserView │
└─────────────┘     └──────────┘     └──────────┘
┌──────────────────┐     ┌────────────┐
│ GET /sprints/:id │────▶│ SprintView │
└──────────────────┘     └────────────┘
```

[fastapi-voyager](https://github.com/allmonday/fastapi-voyager) renders your endpoints, schemas, and entity relationships as a navigable graph. When used with pydantic-resolve's ER Diagram, it also displays entity-level relationship diagrams.

## Install

```bash
pip install fastapi-voyager
```

## Step 1: Mount Voyager

Add one line to your FastAPI app:

```python
from fastapi import FastAPI
from fastapi_voyager import create_voyager

app = FastAPI()

app.mount('/voyager', create_voyager(app))  # (1)
```

1.  Open `/voyager` in your browser to see the interactive graph of all endpoints and their dependencies.

## Step 2: Add ER Diagram

When you have an `ErDiagram` from pydantic-resolve, pass it to visualize entity relationships alongside your API structure:

```python
from pydantic_resolve import ErDiagram, Entity, Relationship

diagram = ErDiagram(  # (1)
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

app.mount('/voyager', create_voyager(app, er_diagram=diagram))  # (2)
```

1.  Define the same `ErDiagram` you use for `AutoLoad` and GraphQL.
2.  Voyager renders a combined view: API endpoints and their underlying entity relationships. Open `/voyager` and switch to the ER Diagram tab to explore.

## Step 3: Configure Options

`create_voyager` accepts optional parameters to customize the visualization:

```python
app.mount(
    '/voyager',
    create_voyager(
        app,
        module_color={'src.services': 'tomato'},      # (1)
        module_prefix='src.services',                   # (2)
        swagger_url="/docs",                            # (3)
        initial_page_policy='first',                    # (4)
        online_repo_url='https://github.com/example/my-project/blob/main',  # (5)
        enable_pydantic_resolve_meta=True,              # (6)
    ),
)
```

1.  `module_color` — map module paths to highlight colors.
2.  `module_prefix` — filter to only show routes under this prefix.
3.  `swagger_url` — link to your Swagger docs.
4.  `initial_page_policy` — which page to show first: `'first'` or `'all'`.
5.  `online_repo_url` — base URL for linking nodes to source code in your repository.
6.  `enable_pydantic_resolve_meta` — show `resolve_*` and `post_*` annotations on each schema.

## Interactive Features

### Highlight Dependencies

Click any node to highlight its upstream and downstream dependencies. See which models an endpoint uses, or which endpoints depend on a specific model.

### View Source Code

Double-click a node or route to view its source code. If `online_repo_url` is configured, it can also open the file directly in VS Code.

### Quick Search

Search schemas by name and display their upstream and downstream relationships. Shift+click on a node to search for it immediately.

!!! tip "pydantic-resolve Meta"

    When `enable_pydantic_resolve_meta=True`, toggle the "pydantic resolve meta" view to see `resolve_*` and `post_*` annotations on each schema — useful for understanding the data assembly logic at a glance.

## Command Line Usage

Generate visualizations without running a server:

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

- [Online Demo](https://www.fastapi-voyager.top/voyager/) — Interactive Voyager visualization.
- [GraphQL Demo](https://www.fastapi-voyager.top/graphql) — GraphQL endpoint powered by pydantic-resolve.
