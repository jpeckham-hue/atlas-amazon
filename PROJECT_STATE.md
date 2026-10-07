# Atlas Amazon — Project State Index

Last reviewed: 2026-10-07
Status: navigation index; not a replacement for architecture, version plans, setup guides, baselines, or recorded evidence.

## Start here

Atlas Amazon is an evidence-backed Amazon SEO and listing-optimization engine for KDP books first and general Amazon products through recipes.

The repository currently has one branch, `main`. v0.10 is the current implemented version line. Its live SP-API catalog slice is paused pending credentials, and v0.11 has not started.

GitHub establishes pushed/committed truth only. Do not infer local or uncommitted Codex work from this index.

## Branch directory

| Branch | Responsibility |
| --- | --- |
| `main` | Sole current branch; implementation, architecture, baselines, and forward plans. |

## Canonical roadmap and decisions

- **Current architecture/status:** `main:docs/architecture.md` and `main:README.md`.
- **v0.10 SP-API provisioning/live-slice procedure:** `main:docs/sp-api-setup.md`.
- **v0.11 conditional plan:** `main:docs/v0.11-plan.md`, last clarified by `c21c123406f6b0decfb661102739e4fdaf56c44f`.
- **Rule provenance:** `main:docs/rule-sources.md`.
- **Recorded/synthetic/live comparison evidence:** `main:docs/baselines/` and `main:docs/benchmarks/`.

## Current strategic priority

Complete the v0.10 read-only live catalog slice when SP-API credentials are provisioned, then replay and verify it. v0.11 remains unstarted and conditional on confirmed access to Brand Registry/Brand Analytics or Amazon Ads API.

The v0.11 decisions already recorded are US marketplace only and weekly demand cadence.

## Current blockers / intentional deferrals

- **v0.10 blocker:** SP-API credentials are not provisioned, so the four-call live catalog slice has not run.
- **v0.11 deferral:** do not start until the v0.10 live catalog slice is recorded/replayed.
- **v0.11 source choice:** pending owner confirmation of Brand Registry/Brand Analytics and/or Amazon Ads API access. If neither is available, v0.11 demand-data work is deferred and demand remains explicitly missing.
- Listing writes, publishing, multiple demand providers, Ads bid optimization, and CLI work are outside the current v0.11 scope.

## Latest verified milestone

`8df40a979a0328b61bc873cdb754172ee7111737` completed the v0.10 offline SP-API hardening/replay preparation and reported 792 tests passed with four live-replay tests skipped pending recordings.

The later `c21c123406f6b0decfb661102739e4fdaf56c44f` is a documentation decision milestone: it records the conditional v0.11 access plan and explicitly leaves v0.10 paused and v0.11 unstarted.

## Agent retrieval procedure

1. Read `PROJECT_STATE.md` first.
2. Read `AGENTS.md` when present.
3. Follow explicit branch-qualified paths and verify files/commits before making status claims.
4. Do not rely on code search alone when direct file/commit inspection is available.
5. Distinguish pushed GitHub state from local/uncommitted Codex state.
6. Immediately report stale search, missing refs, access problems, or contradictory state rather than silently falling back to older information.

## Maintenance contract

Update `PROJECT_STATE.md` in the same change set whenever the canonical roadmap/current-state source changes, its location changes, branch responsibilities change, a major priority changes, a major blocker is added/resolved, a significant milestone is formally reached, or a new branch becomes authoritative for part of the project.

Keep this file concise and link to detailed source documents rather than duplicating them. If it becomes stale or contradicts linked sources, flag the problem and verify source truth before continuing.
