# Connect to UI

Pydantic can generate JSON schemas that support the OpenAPI specification. This means it can convey information such as types and methods across languages.

If using FastAPI, you can refer to the [documentation](https://fastapi.tiangolo.com/advanced/generate-clients/?h=openapi.json#preprocess-the-openapi-specification-for-the-client-generator) to directly generate a TypeScript frontend SDK.

This allows backend changes to be directly passed to the frontend.

A simple example can be found in the repo: [pydantic-resolve-demo](https://github.com/allmonday/pydantic-resolve-demo)

With the assistance of OpenAPI and SDK generation, the cost of front-end and back-end integration is significantly reduced.

When the backend data structure changes, the frontend can immediately detect the changes with TypeScript upon synchronization.
