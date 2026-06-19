"""FastAPI application entry point.

Phase 1: Voyager (ER diagram)
Phase 2: + GraphQL
Phase 3: + REST + MCP
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from src.database import init_db

# ── MCP apps (must be created before lifespan to combine lifespans) ───

from pydantic_resolve import GraphQLHandler, SchemaBuilder  # noqa: E402
from pydantic_resolve.use_case import (  # noqa: E402
    UseCaseAppConfig,
    create_use_case_graphql_mcp_server,
)
from src.entities import diagram  # noqa: E402
from src.service.sprint.service import SprintService  # noqa: E402
from src.service.task.service import TaskService  # noqa: E402

graphql_handler = GraphQLHandler(
    er_diagram=diagram,
    enable_from_attribute_in_type_adapter=True,
)
schema_builder = SchemaBuilder(diagram)

use_case_mcp = create_use_case_graphql_mcp_server(
    apps=[
        UseCaseAppConfig(
            name="template",
            services=[TaskService, SprintService],
            description="Task & Sprint business services",
        ),
    ],
    name="Template UseCase GraphQL MCP",
)
use_case_mcp_http = use_case_mcp.http_app(
    path="/",
    transport="streamable-http",
    stateless_http=True,
)


# ── FastAPI app ──────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with use_case_mcp_http.lifespan(use_case_mcp_http):
        yield


app = FastAPI(
    title="pydantic-resolve Template",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Voyager visualization (Phase 1) ──────────────────────────────────

from fastapi_voyager import create_voyager  # noqa: E402

app.mount("/voyager", create_voyager(app, er_diagram=diagram))


# ── GraphQL endpoints (Phase 2+) ─────────────────────────────────────


class GraphQLRequest(BaseModel):
    query: str


@app.get("/graphql", response_class=HTMLResponse)
async def graphiql():
    return graphql_handler.get_graphiql_html()


@app.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    return await graphql_handler.execute(query=req.query)


@app.get("/schema", response_class=PlainTextResponse)
async def graphql_schema():
    return schema_builder.build_schema()


# ── REST router (Phase 3) ────────────────────────────────────────────

from src.router import api as api_router  # noqa: E402

app.include_router(api_router.route)


# ── MCP mount (Phase 3) ──────────────────────────────────────────────

app.mount("/mcp-usecase", use_case_mcp_http)
