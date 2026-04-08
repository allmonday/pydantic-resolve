# Source Mapping

[中文版](./source_mapping.zh.md) | [docs](./index.md)

This page maps the earlier `docs_old/` documentation into the current `docs/` structure. Overlapping material has been consolidated into one progressive path with cleaner hand-offs.

## Main Path Mapping

| Existing source | docs destination | Action | Notes |
|---|---|---|---|
| `README.md` | all main pages | mine and split | Primary reference for pacing, scenario, and concept order |
| `README.zh.md` | all `.zh.md` main pages | mine and split | Primary Chinese wording reference for the new path |
| `docs_old/install.md` | `quick_start.md` | fold in | Keep installation next to first value |
| `docs_old/introduction.md` | `quick_start.md`, `core_api.md`, `erd_and_autoload.md` | split | Current page mixes motivation, core model, and ERD |
| `docs_old/dataloader.md` | `quick_start.md`, `core_api.md` | split | Keep N+1, batching, and `build_*` details early |
| `docs_old/expose_and_collect.md` | `cross_layer_data_flow.md` | rewrite | Keep concept, replace scenario |
| `docs_old/erd_driven.md` | `erd_and_autoload.md` | rewrite and compress | Keep ERD scaling story, remove unrelated detours |
| `docs_old/schema_first.md` | `erd_and_autoload.md` | merge | No longer a separate stop in the main path |
| `docs_old/graphql.md` | `graphql_and_mcp.md` | reframe | Present as ERD reuse, not an independent entry point |

## Supplemental Mapping

| Existing source | Destination role | Action | Notes |
|---|---|---|---|
| `docs_old/api.md` | reference | keep external for now | Still best treated as reference material |
| `docs_old/migration.md` | reference | migrated into `docs/` | Important reference page now copied into the new path |
| `docs_old/changelog.md` | reference | migrated into `docs/` | Historical record now copied into the new path |
| `docs_old/why.md` | supplemental | bridge later | Motivation should not interrupt onboarding |
| `docs_old/connect_to_ui.md` | supplemental | bridge later | Useful integration topic, but not core learning |
| `docs_old/use_case.md` | appendix candidate | mine selectively | Useful positioning material, but not main path |
| `docs_old/inherit_reuse.md` | advanced future page | postpone | Should not land before the main path stabilizes |

## Page-by-Page Source Reference

| docs page | Main source set | Rewrite intent |
|---|---|---|
| `index.md` | `README.md`, `mkdocs.yml` | explain the new sequence and boundaries |
| `scenario_contract.md` | `README.md`, `README.zh.md` | freeze naming, scenario, and terminology |
| `quick_start.md` | `README.md`, `docs_old/install.md`, `docs_old/dataloader.md` | first value from one N+1 problem |
| `core_api.md` | `README.md`, `docs_old/introduction.md`, `docs_old/dataloader.md` | expand from one field to one nested tree |
| `post_processing.md` | `README.md` | explain `post_*` timing and responsibility |
| `cross_layer_data_flow.md` | `README.md`, `docs_old/expose_and_collect.md` | keep concept, unify scenario |
| `erd_and_autoload.md` | `README.md`, `docs_old/erd_driven.md`, `docs_old/schema_first.md` | frame ERD as scaling step |
| `graphql_and_mcp.md` | `README.md`, `docs_old/graphql.md` | show reuse of the same graph |
| `reference_bridge.md` | `docs_old/api.md`, `docs_old/migration.md`, `docs_old/why.md`, `docs_old/connect_to_ui.md` | clarify where the tutorial path ends |

## How to Use This File

This page provides a migration matrix between the earlier topic-based split and the current progressive path. Use it when you need to trace where a topic was moved or when aligning translations.