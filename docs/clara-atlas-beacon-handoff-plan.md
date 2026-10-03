# Clara ↔ Beacon Pass-Over Test — Design Note

Status: **DEFERRED UNTIL BEACON EXTERNAL-REQUIREMENTS RESEARCH CHECKPOINT**

Date: 2026-10-03

## Why this note exists

Clara Skye's modernization has reached a real cross-project dependency.

Clara has established its own product truth and has completed the upstream authority chain for interior production:

```text
human approval
→ exact-byte frozen page
→ authoritative ordered set
→ verified assembly contract
```

Clara's Target #2 Phase 8 then identified the next missing input: **current external publishing-platform truth** for a KDP interior. Clara deliberately did not invent or freeze those mutable requirements.

Beacon is the natural owner of researching dated, sourced Amazon/KDP truth. Atlas should eventually own the routing/handoff between the independent systems.

The intended first real cross-project vertical slice is therefore:

```text
Clara
  → requirements request
Atlas
  → routes request
Beacon
  → researches current Amazon/KDP truth
  → emits evidence-backed requirements artifact
Atlas
  → verifies/routes artifact
Clara
  → consumes artifact as external input to its export-profile work
```

This note is a design target, not an instruction to implement the handoff now.

## Natural checkpoint before the handoff test

Do **not** interrupt Beacon's current development merely to build Atlas integration.

Beacon is ready for the pass-over test when it can complete one real **External Requirements Research Slice**:

> Given a scoped request for current Amazon/KDP rules, Beacon can research the relevant official sources and emit a stable, structured, evidence-backed result artifact.

For the Clara trial, the request should be approximately:

> Determine the current KDP interior requirements relevant to an 8.5 × 8.5 inch children's activity-book interior, restricted to the specific unresolved export facts supplied by Clara.

The checkpoint is about the capability shape, not about finishing all of Beacon.

## Minimum Beacon capability required

Before Atlas integration, Beacon should be able to:

1. accept a bounded external-requirements research request;
2. research current authoritative Amazon/KDP sources;
3. distinguish sourced platform facts from inference, heuristic, conflict, and unknown;
4. preserve source URL, source identity/title where available, retrieval/verification date, marketplace/scope, and evidence;
5. represent conflicts and unresolved questions explicitly;
6. produce deterministic/stable serialization of the result;
7. validate the result fail-closed;
8. avoid silently substituting historical or heuristic rules for current verified truth.

Beacon already has useful foundations for this direction: dated/sourced `SourceRef` rule provenance, evidence identity/serialization/storage, recipe rule sourcing, research orchestration, and deterministic validation. Reuse those concepts where they genuinely fit rather than creating a parallel evidence system.

## Clara's first request

Clara Phase 8 identified the unresolved external facts. The handoff test should preserve Clara's exact bounded question set rather than asking Beacon to "research KDP" generally.

Expected areas include, subject to the Phase 8 artifact being the authoritative request:

- current acceptance of the intended 8.5 × 8.5 interior trim;
- accepted/required interior artifact/file format and material PDF constraints;
- bleed/no-bleed and page-geometry/page-box rules;
- current resolution/DPI/PPI requirements;
- current color-space/profile requirements;
- compression/downsampling rules if specified;
- font-embedding requirements if relevant to the chosen interior representation;
- page-count/parity constraints;
- blank-page rules if any;
- previewer/proof requirements that materially affect artifact acceptance.

Cover requirements and marketplace metadata are explicitly outside this first pass-over test.

The Clara Phase 8 evidence package remains the authority for the exact request. Beacon must not broaden the request on its own.

## Proposed request artifact

Do not freeze this schema until the vertical slice is implemented and falsified.

Minimum conceptual content:

```text
request identity
requesting system = Clara
request purpose/scope
target platform/product = KDP interior
marketplace/jurisdiction if relevant
bounded questions
requested evidence standard
request version
```

Atlas should route the request; Atlas should not rewrite Clara's domain question.

## Proposed Beacon result artifact

Again, this is a design sketch, not a production schema.

For each requested question Beacon should be able to return something conceptually equivalent to:

```text
question identity
status:
  VERIFIED
  CONFLICTING
  UNKNOWN
  NOT_SPECIFIED_BY_SOURCE
claim/value when supported
scope
source reference(s)
verified/retrieved date
evidence identity
notes limited to interpretation needed to understand the source
```

The overall artifact should also carry:

```text
request identity/reference
Beacon result identity/version
run/build identity
artifact/content hash
completion status
unresolved question set
```

Do not duplicate raw evidence if stable evidence references are sufficient.

## Ownership boundaries

### Clara owns

- what the book is;
- intended product/trim decisions;
- which external questions it needs answered;
- its eventual export-profile interpretation;
- whether external facts have upstream consequences for page production;
- final product/publishing decisions.

### Beacon owns

- external Amazon/KDP research;
- source/evidence capture;
- verification date and scope;
- classification of verified/conflicting/unknown external facts;
- reproducible evidence-backed result artifacts.

Beacon does **not** decide Clara's product design.

### Atlas owns

- routing a request to the appropriate system;
- preserving request/result identity across the handoff;
- verifying that the returned artifact corresponds to the requested job;
- making the verified result available to the requesting system;
- cross-project handoff provenance/lineage.

Atlas should not become the owner of Amazon rules or Clara product truth.

## First pass-over acceptance test

When Beacon reaches the External Requirements Research Slice checkpoint:

1. Clara emits one bounded KDP-interior requirements request derived from Phase 8.
2. Atlas routes it to Beacon without changing the question semantics.
3. Beacon performs the research and produces one evidence-backed result artifact.
4. Atlas verifies that the returned artifact:
   - answers the same request identity/version;
   - is structurally valid;
   - preserves evidence references;
   - has a stable content identity/hash;
   - explicitly reports unresolved/conflicting items.
5. Atlas passes the verified result to Clara.
6. Clara consumes it as **external platform evidence**, not as Clara-owned product truth.
7. Clara uses it in the next export-profile falsification step.
8. Replaying/rerouting the same completed artifact must not silently change its meaning.
9. A later Beacon refresh must create a new dated/versioned result rather than rewriting historical evidence.

## Failure cases the vertical slice should test

At minimum:

- unknown request identity;
- request/result version mismatch;
- result for the wrong requesting system/job;
- malformed result;
- missing required evidence for a VERIFIED claim;
- stale or superseded result being mistaken for a newer verification;
- conflicting source state hidden as VERIFIED;
- UNKNOWN silently replaced by a default;
- artifact hash/content mismatch;
- duplicate delivery/idempotent replay;
- Beacon result broadened beyond Clara's request and treated as requested truth.

## What not to build yet

Do not build:

- a general inter-agent message bus;
- a distributed workflow engine;
- a shared database;
- a generic event system;
- universal cross-project schemas;
- automatic writes to KDP;
- automatic Clara export changes;
- a Beacon dependency inside Clara;
- a Clara dependency inside Beacon.

The first implementation should be the smallest artifact-based handoff that proves the real Clara → Atlas → Beacon → Atlas → Clara path.

Generalize only after another real cross-project consumer earns it.

## Stop point

When Beacon can reliably produce the evidence-backed external-requirements artifact described above, **stop Beacon feature development for this thread and run the Atlas pass-over experiment**.

That is the natural integration checkpoint.

The handoff test succeeds when Clara can receive current, sourced, dated KDP truth from Beacon through Atlas without:

- Clara learning how Beacon researches;
- Beacon learning Clara's internal architecture;
- Atlas owning either system's domain truth;
- Jeff manually translating the result between projects.

## Architectural principle

**Systems should exchange verified artifacts, not share each other's internals.**

For this first real case:

```text
Clara owns the question.
Beacon owns the external evidence.
Atlas owns the handoff.
```
