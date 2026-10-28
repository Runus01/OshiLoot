# 1. One deployable backend with enforced module boundaries

Status: accepted, October 2026

## Context

The backend has four jobs: read a MyAnimeList list (anime), find merch across stores
(merch), supply countries and exchange rates (regions), and record outbound clicks (go).
I first planned these as four microservices, each its own Lambda function.

For one developer and low traffic, separate services would mean four deploy targets,
four sets of cold starts, and debugging across process boundaries, while the main benefit
of microservices — teams shipping independently — doesn't apply.

## Decision

Build one FastAPI application, deployed as one container image to one Lambda function,
split into modules that behave like services inside the codebase:

- Each module (`app/anime`, `app/merch`, `app/regions`, `app/go`) owns its routes, models
  and logic, and exposes only its router.
- Modules never import each other. They share only `app/core` (config, storage, HTTP
  client, link signing). `import-linter` enforces this in CI, so a boundary violation fails
  the build rather than relying on discipline.
- Where one module needs another's data, the browser passes it along. The merch module
  receives anime titles as query parameters instead of calling the anime module.
- External dependencies sit behind interfaces (`AnimeSource`, `StoreAdapter`), so a new
  store or a switch from MyAnimeList to AniList is a new adapter, not a rewrite.

## Consequences

- One image, one function, one log group, one deploy. Cold starts happen once, not four
  times.
- A slow or failing store can't block the rest: the merch module gives each store a
  deadline and returns partial results with a status per store.
- All modules scale together. At this traffic that costs nothing; if one module ever needs
  different scaling or memory, it can be extracted into its own function. Because it already
  has no imports from its siblings, extraction is mostly a deployment change.
- Signals that would justify splitting a module out: it needs a different runtime or memory
  size, it deploys far more often than the rest, or another team takes it over.
