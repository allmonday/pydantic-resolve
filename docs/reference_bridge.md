# Reference Bridge

[中文版](./reference_bridge.zh.md) | [docs](./index.md)

The main `docs/` path ends here. From this point on, the reader usually wants one of two things:

- deeper API detail
- broader project context

Those are valid needs, but they are different from onboarding. That is why they should live outside the first-read tutorial path.

## Where to Go Next

| Need | Read Next | Why |
|---|---|---|
| Detailed API surface | `docs_old/api.md` | Constructor arguments, utility APIs, loader metadata, and lower-level behavior |
| Upgrading between versions | `docs/migration.md` | Migration concerns are important, but not part of the core teaching path |
| Release history | `docs/changelog.md` | Useful after you already know the concepts |
| Project motivation | `docs/why.md` | Explains why the library exists and what tradeoffs shaped it |
| UI and SDK integration | `docs/connect_to_ui.md` | Integration detail for teams working with OpenAPI and clients |

## Suggested Second-Pass Reading Order

If you finished the main path and want a sensible next sequence, this order is usually the most useful:

1. API reference
2. migration guide
3. GraphQL framework details
4. project motivation
5. UI integration notes

## What Still Lives in `docs_old/`

For now, the more reference-style material that has not been migrated yet still lives in `docs_old/`. `docs/` is focused on the new progressive learning path first.

That means:

- `docs/` is the new tutorial-oriented path
- `docs_old/` still contains older reference and topic-based material

## What May Move Later

Future `docs/` iterations may absorb or reorganize topics such as:

- inheritance and reuse patterns
- framework-specific integration guides
- API reference refinements

But those topics should be moved only after the main path is already stable.