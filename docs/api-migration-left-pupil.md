# API Automation Migration: `/api-engine` -> `/left-pupil`

`/left-pupil` is the primary API automation surface.
`/api-engine` remains available for compatibility and is deprecated.

## Endpoint mapping

| Deprecated (`/api-engine`) | Primary (`/left-pupil`) | Notes |
|---|---|---|
| `POST /execute` | `POST /execute` | request payload differs (`api_ir` wrapper vs direct step model) |
| `POST /execute/chain` | `POST /execute-chain` | chain schema differs |
| `POST /swagger/parse` | `POST /parse-swagger` | output shape differs slightly |
| `POST /swagger/generate-ir` | `POST /generate-ir` | `/left-pupil` supports template generation |

## Header signals on deprecated routes

Deprecated compatibility endpoints now return:

- `Deprecation: true`
- `Sunset: 2026-09-30`
- `Link: </docs/api-migration-left-pupil.md>; rel="deprecation"`

## Recommended migration order

1. Move Swagger parsing calls to `/left-pupil/parse-swagger`.
2. Move single-step execution to `/left-pupil/execute`.
3. Move chain execution to `/left-pupil/execute-chain`.
4. Remove `/api-engine` usage after sunset date.
